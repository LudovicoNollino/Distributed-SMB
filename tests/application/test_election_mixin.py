"""Unit tests for ElectionMixin — role promotion after leader election."""

import json
import time

from distributed_smb.application.election import ElectionCoordinator, EnvironmentalStateBuffer
from distributed_smb.application.node_controller import NodeController
from distributed_smb.shared.config import (
    ELECTION_CLAIM_TIMEOUT_S,
    GAME_EVENT_WS_PORT,
    HOST_UDP_PORT,
    T_ELECTION_BASE_S,
    T_ELECTION_DELTA_S,
)
from distributed_smb.shared.enums import MessageType, PlayerRole
from distributed_smb.shared.messages.election import ElectionAck, NewHostClaim
from distributed_smb.shared.roster import GlobalRoster, RosterEntry

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class SpyBroker:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.promoted_port: int | None = None
        self.reconnected_to: tuple[str, int] | None = None

    def send(self, payload: bytes) -> None:
        self.sent.append(payload)

    def get_disconnected_player(self) -> str | None:
        return None

    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        pass

    def reconnect(self, host: str, port: int) -> None:
        self.reconnected_to = (host, port)

    def promote_to_server(self, port: int) -> None:
        self.promoted_port = port

    def last_message_type(self) -> str | None:
        if not self.sent:
            return None
        return json.loads(self.sent[-1]).get("message_type")


def _make_controller(
    local_ip: str = "10.0.0.2",
    local_player_id: str = "player2",
    join_index: int = 1,
    with_host_in_roster: bool = True,
) -> tuple[NodeController, SpyBroker]:
    broker = SpyBroker()
    nc = NodeController(game_event_broker=broker)
    nc.bootstrap(role=PlayerRole.CLIENT)
    nc.local_ip = local_ip
    nc.local_player_id = local_player_id
    nc.join_index = join_index
    nc.session_id = "test-session"

    if with_host_in_roster:
        nc.roster.add_player(
            RosterEntry(
                player_id="player1",
                host="10.0.0.1",
                udp_port=HOST_UDP_PORT,
                join_index=0,
                is_host=True,
            )
        )
    nc.roster.add_player(
        RosterEntry(
            player_id=local_player_id,
            host=local_ip,
            udp_port=50011,
            join_index=join_index,
            is_host=False,
        )
    )
    nc.election_coordinator = ElectionCoordinator(
        join_index=join_index,
        my_ip=local_ip,
        timeout_base_s=T_ELECTION_BASE_S,
        timeout_delta_s=T_ELECTION_DELTA_S,
    )
    nc.env_state_buffer = EnvironmentalStateBuffer()
    return nc, broker


# ---------------------------------------------------------------------------
# _on_self_elected
# ---------------------------------------------------------------------------


class TestOnSelfElected:
    def test_no_peers_promotes_immediately(self):
        """Sole surviving client promotes without broadcasting a claim."""
        from distributed_smb.application.election import SelfElected

        nc, broker = _make_controller()
        # No other clients in roster → _known_client_peers() returns empty set
        event = SelfElected(my_ip="10.0.0.2")
        nc._on_self_elected(event)

        assert nc._promotion_done is True
        assert nc.role is PlayerRole.HOST
        assert broker.promoted_port == GAME_EVENT_WS_PORT

    def test_with_peers_broadcasts_claim(self):
        """With surviving peers, NewHostClaim is broadcast and promotion deferred."""
        from distributed_smb.application.election import SelfElected

        nc, broker = _make_controller()
        # Add a second client peer
        nc.roster.add_player(
            RosterEntry(
                player_id="player3",
                host="10.0.0.3",
                udp_port=50012,
                join_index=2,
            )
        )

        event = SelfElected(my_ip="10.0.0.2")
        nc._on_self_elected(event)

        assert nc._promotion_done is False
        assert nc.role is PlayerRole.CLIENT
        assert broker.last_message_type() == MessageType.NEW_HOST_CLAIM.value
        assert nc._pending_election_acks == {"10.0.0.3"}

    def test_claim_deadline_is_set(self):
        from distributed_smb.application.election import SelfElected

        nc, broker = _make_controller()
        nc.roster.add_player(
            RosterEntry(
                player_id="player3",
                host="10.0.0.3",
                udp_port=50012,
                join_index=2,
            )
        )
        before = time.time()
        nc._on_self_elected(SelfElected(my_ip="10.0.0.2"))

        assert nc._election_claim_deadline >= before + ELECTION_CLAIM_TIMEOUT_S - 0.1


# ---------------------------------------------------------------------------
# _on_election_ack
# ---------------------------------------------------------------------------


class TestOnElectionAck:
    def test_full_quorum_triggers_promotion(self):
        """Receiving acks from all pending peers triggers promotion."""
        nc, broker = _make_controller()
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() + ELECTION_CLAIM_TIMEOUT_S

        nc._on_election_ack(ElectionAck(from_ip="10.0.0.3", session_id="test-session"))

        assert nc._promotion_done is True
        assert nc.role is PlayerRole.HOST

    def test_partial_ack_no_premature_promote(self):
        """A single ack when two are pending does not promote."""
        nc, broker = _make_controller()
        nc._pending_election_acks = {"10.0.0.3", "10.0.0.4"}
        nc._election_claim_deadline = time.time() + ELECTION_CLAIM_TIMEOUT_S

        nc._on_election_ack(ElectionAck(from_ip="10.0.0.3", session_id="test-session"))

        assert nc._promotion_done is False
        assert nc.role is PlayerRole.CLIENT
        assert nc._pending_election_acks == {"10.0.0.4"}

    def test_unknown_ip_ignored(self):
        """Ack from an IP not in the pending set is silently discarded."""
        nc, broker = _make_controller()
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() + ELECTION_CLAIM_TIMEOUT_S

        nc._on_election_ack(ElectionAck(from_ip="10.0.0.99", session_id="test-session"))

        assert nc._promotion_done is False
        assert nc._pending_election_acks == {"10.0.0.3"}

    def test_idempotent_after_promotion(self):
        """Extra acks after promotion are ignored."""
        nc, broker = _make_controller()
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() + ELECTION_CLAIM_TIMEOUT_S
        nc._on_election_ack(ElectionAck(from_ip="10.0.0.3", session_id="test-session"))
        promoted_role = nc.role

        nc._on_election_ack(ElectionAck(from_ip="10.0.0.3", session_id="test-session"))  # duplicate

        assert nc.role is promoted_role


# ---------------------------------------------------------------------------
# _on_new_host_claim
# ---------------------------------------------------------------------------


class TestOnNewHostClaim:
    def test_follower_sends_election_ack(self):
        """Receiving a legitimate claim yields the coordinator and sends ElectionAck."""
        nc, broker = _make_controller(local_ip="10.0.0.3", local_player_id="player3", join_index=2)
        t0 = time.time()
        nc.election_coordinator.start_election({"10.0.0.2"})
        nc.election_coordinator.set_election_timer(t0)

        msg = NewHostClaim(claimer_ip="10.0.0.2", claimer_join_index=1, session_id="test-session")
        nc._on_new_host_claim(msg)

        assert broker.last_message_type() == MessageType.ELECTION_ACK.value

    def test_own_broadcast_echo_ignored(self):
        """A NewHostClaim from our own IP is discarded (relay echo)."""
        nc, broker = _make_controller(local_ip="10.0.0.2", join_index=1)
        msg = NewHostClaim(claimer_ip="10.0.0.2", claimer_join_index=1, session_id="test-session")
        nc._on_new_host_claim(msg)

        assert not broker.sent


# ---------------------------------------------------------------------------
# _tick_claim_deadline
# ---------------------------------------------------------------------------


class TestTickClaimDeadline:
    def test_deadline_not_yet_reached_no_action(self):
        nc, broker = _make_controller()
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() + 10.0

        nc._tick_claim_deadline(time.time())

        assert nc._promotion_done is False

    def test_deadline_passed_removes_unresponsive_and_promotes(self):
        """After deadline, silent peer is removed from roster and node promotes."""
        nc, broker = _make_controller()
        nc.roster.add_player(
            RosterEntry(
                player_id="player3",
                host="10.0.0.3",
                udp_port=50012,
                join_index=2,
            )
        )
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() - 0.1  # already in the past

        nc._tick_claim_deadline(time.time())

        assert nc._promotion_done is True
        assert nc.role is PlayerRole.HOST
        assert nc.roster.get_player("player3") is None


# ---------------------------------------------------------------------------
# _promote_to_host
# ---------------------------------------------------------------------------


class TestPromoteToHost:
    def test_role_switches_to_host(self):
        nc, broker = _make_controller()
        nc._promote_to_host()
        assert nc.role is PlayerRole.HOST

    def test_idempotent(self):
        """Calling _promote_to_host twice does not promote_to_server twice."""
        nc, broker = _make_controller()
        nc._promote_to_host()
        broker.promoted_port = None

        nc._promote_to_host()

        assert broker.promoted_port is None  # second call was a no-op

    def test_crashed_host_removed_from_roster(self):
        nc, broker = _make_controller(with_host_in_roster=True)
        nc._promote_to_host()
        assert nc.roster.get_player("player1") is None

    def test_self_marked_as_host_in_roster(self):
        nc, broker = _make_controller()
        nc._promote_to_host()
        assert nc.roster.get_host().player_id == "player2"

    def test_promote_to_server_called(self):
        nc, broker = _make_controller()
        nc._promote_to_host()
        assert broker.promoted_port == GAME_EVENT_WS_PORT

    def test_reconnection_ack_broadcast_to_peers(self):
        """If surviving peers exist, a ReconnectionAck is broadcast."""
        nc, broker = _make_controller()
        nc.roster.add_player(
            RosterEntry(
                player_id="player3",
                host="10.0.0.3",
                udp_port=50012,
                join_index=2,
            )
        )
        nc._promote_to_host()

        sent_types = [json.loads(p).get("message_type") for p in broker.sent]
        assert MessageType.RECONNECTION_ACK.value in sent_types

    def test_no_reconnection_ack_when_sole_survivor(self):
        """No ReconnectionAck broadcast when there are no other peers."""
        nc, broker = _make_controller()
        # Only the local player and old host in roster; old host will be removed
        nc._promote_to_host()

        sent_types = [json.loads(p).get("message_type") for p in broker.sent]
        assert MessageType.RECONNECTION_ACK.value not in sent_types


# ---------------------------------------------------------------------------
# GlobalRoster.promote_host
# ---------------------------------------------------------------------------


class TestPromoteHost:
    def _make_roster(self) -> GlobalRoster:
        r = GlobalRoster()
        r.add_player(
            RosterEntry(player_id="p1", host="10.0.0.1", udp_port=50010, join_index=0, is_host=True)
        )
        r.add_player(RosterEntry(player_id="p2", host="10.0.0.2", udp_port=50011, join_index=1))
        return r

    def test_new_host_flagged(self):
        r = self._make_roster()
        r.promote_host("p2")
        assert r.get_player("p2").is_host is True

    def test_old_host_unflagged(self):
        r = self._make_roster()
        r.promote_host("p2")
        assert r.get_player("p1").is_host is False

    def test_get_host_returns_new_host(self):
        r = self._make_roster()
        r.promote_host("p2")
        assert r.get_host().player_id == "p2"
