"""Unit tests for ElectionMixin — role promotion after leader election."""

import json
import time

import pytest

from distributed_smb.application.election import (
    ElectionCoordinator,
    EnvironmentalStateBuffer,
    HostTimeoutWatcher,
)
from distributed_smb.application.node_controller import NodeController
from distributed_smb.domain.world import CharacterState
from distributed_smb.network.udp_handler import UdpHandler
from distributed_smb.shared.config import (
    ELECTION_CLAIM_TIMEOUT_S,
    GAME_EVENT_WS_PORT,
    HOST_TIMEOUT_S,
    HOST_UDP_PORT,
    HOST_VERIFY_TIMEOUT_S,
    RECONNECTION_FALLBACK_TIMEOUT_S,
    T_ELECTION_BASE_S,
    T_ELECTION_DELTA_S,
)
from distributed_smb.shared.enums import MessageType, PlayerRole
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.election import ElectionAck, NewHostClaim
from distributed_smb.shared.messages.recovery import HostIdentityResponse
from distributed_smb.shared.messages.session import SessionCreated, SessionRecreate
from distributed_smb.shared.roster import GlobalRoster, RosterEntry

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeWsHandler:
    """WsHandler stub — connect/send/poll/close are no-ops; auto-acks SessionRecreate."""

    def __init__(self):
        self.sent: list = []
        self._queue: list = []

    def connect(self, timeout: float = 10.0) -> None:
        pass

    def send(self, message) -> None:
        self.sent.append(message)
        if isinstance(message, SessionRecreate):
            self._queue.append(SessionCreated(session_id=message.session_id, join_index=0))

    def poll(self):
        return self._queue.pop(0) if self._queue else None

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _no_election_sleep(monkeypatch):
    monkeypatch.setattr("distributed_smb.application.election_mixin.time.sleep", lambda s: None)


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


class SpyLobbyService:
    def __init__(self) -> None:
        self.launched = False

    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        self.launched = True


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
    # Patch out network-touching paths so unit tests never block on real I/O.
    fake_ws = FakeWsHandler()
    nc.ws_handler = fake_ws
    nc._make_lobby_ws_client = lambda host, port: setattr(nc, "ws_handler", FakeWsHandler())
    nc._reconnect_game_event_handler = lambda *a, **kw: None
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
        assert nc.engine.is_authoritative is True

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
        assert nc.engine.is_authoritative is True

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
# Election/reconnection messages must also travel over direct UDP — the WS
# relay dies with a crashed host if it ran the relay container locally,
# which can leave survivors with no way to hear from each other at all
# (each self-elects independently — split brain) unless UDP works too.
# ---------------------------------------------------------------------------


class SpyUdpHandler:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, str, int]] = []

    def send_packet_nowait(self, payload: bytes, remote_host: str, remote_port: int) -> None:
        self.sent.append((payload, remote_host, remote_port))

    def receive_packet_nowait(self):
        return None

    def open_socket(self) -> None:
        pass

    def close_socket(self) -> None:
        pass


class TestElectionMessagesSentDirectlyOverUdp:
    def test_new_host_claim_broadcast_over_udp_to_all_peers(self):
        from distributed_smb.application.election import SelfElected

        nc, _ = _make_controller(local_ip="10.0.0.2", local_player_id="player2", join_index=1)
        nc.roster.add_player(
            RosterEntry(player_id="player3", host="10.0.0.3", udp_port=50013, join_index=2)
        )
        spy = SpyUdpHandler()
        nc.udp_handler = spy

        event = SelfElected(my_ip="10.0.0.2")
        nc._on_self_elected(event)

        # Only the surviving client peer — _known_client_peers() deliberately
        # excludes the (crashed) current host.
        targets = {(host, port) for _, host, port in spy.sent}
        assert targets == {("10.0.0.3", 50013)}
        for payload, _, _ in spy.sent:
            decoded = nc.serializer.decode_message(payload)
            assert isinstance(decoded, NewHostClaim)
            assert decoded.claimer_ip == "10.0.0.2"

    def test_election_ack_sent_directly_only_to_claimer(self):
        nc, _ = _make_controller(local_ip="10.0.0.3", local_player_id="player3", join_index=2)
        nc.roster.add_player(
            RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50012, join_index=1)
        )
        nc.election_coordinator.start_election({"10.0.0.2"})
        nc.election_coordinator.set_election_timer(time.time())
        spy = SpyUdpHandler()
        nc.udp_handler = spy

        msg = NewHostClaim(claimer_ip="10.0.0.2", claimer_join_index=1, session_id="test-session")
        nc._on_new_host_claim(msg)

        assert len(spy.sent) == 1
        payload, host, port = spy.sent[0]
        assert (host, port) == ("10.0.0.2", 50012)
        decoded = nc.serializer.decode_message(payload)
        assert isinstance(decoded, ElectionAck)
        assert decoded.from_ip == "10.0.0.3"

    def test_reconnection_ack_sent_directly_after_promotion(self, monkeypatch):
        from distributed_smb.network.udp_handler import UdpHandler
        from distributed_smb.shared.messages.election import ReconnectionAck

        sent: list[tuple[bytes, str, int]] = []

        def spy_send(self, payload, remote_host, remote_port):
            sent.append((payload, remote_host, remote_port))

        monkeypatch.setattr(UdpHandler, "send_packet_nowait", spy_send)

        nc, _ = _make_controller(local_ip="10.0.0.2", local_player_id="player2", join_index=1)
        nc.roster.add_player(
            RosterEntry(player_id="player3", host="10.0.0.3", udp_port=50013, join_index=2)
        )

        nc._promote_to_host()

        acks = [
            nc.serializer.decode_message(payload) for payload, host, _ in sent if host == "10.0.0.3"
        ]
        reconnection_acks = [ack for ack in acks if isinstance(ack, ReconnectionAck)]
        assert len(reconnection_acks) == 1
        assert reconnection_acks[0].new_host_ip == "10.0.0.2"


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

    def test_follower_records_following_state_for_fallback(self):
        """Following a claim starts the ReconnectionAck fallback deadline."""
        nc, _ = _make_controller(local_ip="10.0.0.3", local_player_id="player3", join_index=2)
        nc.election_coordinator.start_election({"10.0.0.2"})
        nc.election_coordinator.set_election_timer(time.time())

        before = time.time()
        msg = NewHostClaim(claimer_ip="10.0.0.2", claimer_join_index=1, session_id="test-session")
        nc._on_new_host_claim(msg)

        assert nc._following_host_ip == "10.0.0.2"
        assert nc._following_since >= before


# ---------------------------------------------------------------------------
# _tick_reconnection_fallback — direct UDP probe when ReconnectionAck never
# arrives because the crashed host's own relay went down with it.
# ---------------------------------------------------------------------------


class FakeRecoveryProber:
    def __init__(self, found_ip: str | None) -> None:
        self.found_ip = found_ip
        self.calls: list = []

    def find_current_host(self, session_id, requester_ip, peers, timeout_per_peer):
        self.calls.append((session_id, requester_ip, list(peers), timeout_per_peer))
        return self.found_ip


class TestTickReconnectionFallback:
    def test_no_action_before_timeout_elapses(self):
        nc, _ = _make_controller()
        prober = FakeRecoveryProber(found_ip="10.0.0.2")
        nc.recovery_prober = prober
        nc._following_host_ip = "10.0.0.2"
        nc._following_since = time.time()

        nc._tick_reconnection_fallback(time.time())

        assert not prober.calls
        assert nc.reconnected is False

    def test_no_action_when_already_reconnected(self):
        nc, _ = _make_controller()
        prober = FakeRecoveryProber(found_ip="10.0.0.2")
        nc.recovery_prober = prober
        nc.reconnected = True
        nc._following_host_ip = "10.0.0.2"
        nc._following_since = time.time() - RECONNECTION_FALLBACK_TIMEOUT_S - 0.1

        nc._tick_reconnection_fallback(time.time())

        assert not prober.calls

    def test_no_action_without_a_pending_follow(self):
        nc, _ = _make_controller()
        prober = FakeRecoveryProber(found_ip="10.0.0.2")
        nc.recovery_prober = prober

        nc._tick_reconnection_fallback(time.time())

        assert not prober.calls

    def test_probes_directly_after_timeout_and_completes_reconnection(self):
        nc, _ = _make_controller()
        prober = FakeRecoveryProber(found_ip="10.0.0.2")
        nc.recovery_prober = prober
        nc._following_host_ip = "10.0.0.2"
        nc._following_since = time.time() - RECONNECTION_FALLBACK_TIMEOUT_S - 0.1

        nc._tick_reconnection_fallback(time.time())

        assert prober.calls
        assert nc.reconnected is True
        assert nc.remote_host == "10.0.0.2"
        assert nc._following_host_ip is None

    def test_retries_instead_of_giving_up_on_failed_probe(self):
        """A failed probe (candidate not ready yet) keeps the follow state so
        the next tick tries again, rather than stalling forever."""
        nc, _ = _make_controller()
        prober = FakeRecoveryProber(found_ip=None)
        nc.recovery_prober = prober
        nc._following_host_ip = "10.0.0.2"
        nc._following_since = time.time() - RECONNECTION_FALLBACK_TIMEOUT_S - 0.1

        now = time.time()
        nc._tick_reconnection_fallback(now)

        assert nc.reconnected is False
        assert nc._following_host_ip == "10.0.0.2"
        assert nc._following_since == pytest.approx(now, abs=0.5)


# ---------------------------------------------------------------------------
# _tick_election_state — verify-before-electing
# ---------------------------------------------------------------------------


class TestTickElectionStateHostVerify:
    """A snapshot gap alone must not trigger an election — see HOST_VERIFY_TIMEOUT_S:
    a direct probe confirms the host is really gone first, since a brief stall
    (GC pause, CPU contention from other peers/containers on the same machine)
    can otherwise look identical to a crash."""

    def test_timeout_sends_probe_instead_of_electing_immediately(self, monkeypatch):
        nc, _ = _make_controller()
        nc.timeout_watcher = HostTimeoutWatcher(timeout_s=HOST_TIMEOUT_S)
        nc.timeout_watcher.reset(time.time() - HOST_TIMEOUT_S - 0.1)

        sent: list[tuple[str, int]] = []
        monkeypatch.setattr(
            UdpHandler,
            "send_packet_nowait",
            lambda self, payload, host, port: sent.append((host, port)),
        )

        nc._tick_election_state()

        assert nc.election_triggered is False
        assert nc._host_verify_deadline != 0.0
        assert sent == [(nc.remote_host, nc.remote_port)]

    def test_verify_response_cancels_the_election(self, monkeypatch):
        nc, _ = _make_controller()
        nc.timeout_watcher = HostTimeoutWatcher(timeout_s=HOST_TIMEOUT_S)
        nc.timeout_watcher.reset(time.time() - HOST_TIMEOUT_S - 0.1)
        monkeypatch.setattr(UdpHandler, "send_packet_nowait", lambda self, *a, **kw: None)

        nc._tick_election_state()
        assert nc._host_verify_deadline != 0.0

        nc._on_host_identity_response(
            HostIdentityResponse(session_id=nc.session_id, host_ip=nc.remote_host)
        )

        assert nc._host_verify_deadline == 0.0
        nc._tick_election_state()
        assert nc.election_triggered is False

    def test_no_response_within_window_starts_the_election(self, monkeypatch):
        nc, _ = _make_controller()
        nc.timeout_watcher = HostTimeoutWatcher(timeout_s=HOST_TIMEOUT_S)
        nc.timeout_watcher.reset(time.time() - HOST_TIMEOUT_S - 0.1)
        monkeypatch.setattr(UdpHandler, "send_packet_nowait", lambda self, *a, **kw: None)

        nc._tick_election_state()
        assert nc.election_triggered is False

        nc._host_verify_deadline = time.time() - HOST_VERIFY_TIMEOUT_S - 0.1
        nc._tick_election_state()

        assert nc.election_triggered is True
        assert nc._host_verify_deadline == 0.0


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

    def test_deadline_passed_fully_evicts_unresponsive_peer(self):
        """Silent peer is evicted everywhere, not just removed from the roster.

        Regression test for the gap noted in HANDOFF_300626.md: a peer that
        times out during election left ghost entries in world_state and the
        per-player input/timing caches because _tick_claim_deadline used to
        call roster.remove_player() directly instead of _evict_player().
        """
        nc, broker = _make_controller()
        nc.roster.add_player(
            RosterEntry(
                player_id="player3",
                host="10.0.0.3",
                udp_port=50012,
                join_index=2,
            )
        )
        nc.engine.world_state.add_player(CharacterState(player_id="player3"))
        nc.cached_remote_inputs["player3"] = InputState()
        nc.last_remote_input_sequence["player3"] = 5
        nc.last_input_time["player3"] = time.time()
        nc._pending_election_acks = {"10.0.0.3"}
        nc._election_claim_deadline = time.time() - 0.1  # already in the past

        nc._tick_claim_deadline(time.time())

        assert nc.roster.get_player("player3") is None
        assert nc.engine.world_state.get_player("player3") is None
        assert "player3" not in nc.cached_remote_inputs
        assert "player3" not in nc.last_remote_input_sequence
        assert "player3" not in nc.last_input_time


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

    def test_promote_to_host_launches_lobby_and_sends_session_recreate(self, monkeypatch):
        """After promotion, lobby is started and SESSION_RECREATE is sent via ws_handler (M9).

        The lobby re-registration (Docker/lobby WS handshake) runs on a
        background thread so it never freezes the frame loop — join it here
        to make the assertions deterministic instead of racing it.
        """

        class SpyLobbyService:
            def __init__(self):
                self.launched = False

            def launch(self, host="0.0.0.0", port=0):
                self.launched = True

        nc, _ = _make_controller()
        spy_lobby = SpyLobbyService()
        nc.lobby_service = spy_lobby

        fake_ws = FakeWsHandler()
        monkeypatch.setattr(
            "distributed_smb.application.election_mixin.WsHandler",
            lambda *args, **kwargs: fake_ws,
        )

        nc._promote_to_host()
        nc._relaunch_thread.join(timeout=2.0)

        assert spy_lobby.launched
        assert nc.ws_handler is fake_ws
        assert len(fake_ws.sent) == 1
        msg = fake_ws.sent[0]
        assert isinstance(msg, SessionRecreate)
        assert msg.session_id == "test-session"
        # After evicting original host (join_index=0), remaining player is join_index=1 (self).
        # next_join_index must be max(1) + 1 = 2.
        assert msg.next_join_index == 2


# ---------------------------------------------------------------------------
# _on_reconnection_ack — election reset after following a new host
# ---------------------------------------------------------------------------


class TestOnReconnectionAck:
    def _make_following_controller(self) -> NodeController:
        """Controller that has just followed a new host (A crashed, B promoted)."""
        nc, _ = _make_controller(local_ip="10.0.0.3", local_player_id="player3", join_index=2)
        # Add B to the roster (B is the promoted host, still is_host=False in C's stale view)
        nc.roster.add_player(
            RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50011, join_index=1)
        )
        # Simulate state after C followed B in the first election
        nc.election_triggered = True
        return nc

    def test_reconnection_ack_resets_election_triggered(self):
        """After following a new host, election_triggered must be cleared so a future
        host crash can be detected by _tick_election_state."""
        from distributed_smb.shared.messages.election import ReconnectionAck

        nc = self._make_following_controller()
        nc._on_reconnection_ack(
            ReconnectionAck(
                new_host_ip="10.0.0.2",
                udp_port=50010,
                game_events_port=50003,
                session_id="test-session",
            )
        )

        assert nc.election_triggered is False

    def test_reconnection_ack_resets_election_coordinator(self):
        """election_coordinator is set to None so _ensure_election_components re-creates it."""
        from distributed_smb.shared.messages.election import ReconnectionAck

        nc = self._make_following_controller()
        nc._on_reconnection_ack(
            ReconnectionAck(
                new_host_ip="10.0.0.2",
                udp_port=50010,
                game_events_port=50003,
                session_id="test-session",
            )
        )

        assert nc.election_coordinator is None
        assert nc.timeout_watcher is not None  # fresh watcher created

    def test_reconnection_ack_updates_roster(self):
        """Old host (A) is evicted and new host (B) is promoted in the local roster."""
        from distributed_smb.shared.messages.election import ReconnectionAck

        nc = self._make_following_controller()
        # Before: A is is_host=True (stale), B is is_host=False
        assert nc.roster.get_host().player_id == "player1"  # old host A

        nc._on_reconnection_ack(
            ReconnectionAck(
                new_host_ip="10.0.0.2",
                udp_port=50010,
                game_events_port=50003,
                session_id="test-session",
            )
        )

        # A evicted, B promoted
        assert nc.roster.get_player("player1") is None
        assert nc.roster.get_host().player_id == "player2"

    def test_reconnection_ack_resyncs_environment_from_buffered_snapshot(self):
        """A surviving client's local destructible_blocks/power_ups/gates are
        never touched by ordinary reconcile() (see M4 — avoids pop-in on a
        locally-predicted block break). If a BlockDestroyedMessage was lost
        during the crash window (the WS relay can die with the old host),
        this node's local copy silently diverges from every other survivor
        forever, since nothing else ever corrects it. On reconnection it must
        be resynced from the same last-known-good snapshot the new host
        itself bootstraps from — otherwise one client can permanently show a
        block as broken while everyone else (correctly) does not."""
        from distributed_smb.domain.entity import DestructibleBlock
        from distributed_smb.domain.world import EnvironmentalState, WorldState
        from distributed_smb.shared.messages.election import ReconnectionAck
        from distributed_smb.shared.messages.sync import WorldStateSnapshot

        nc = self._make_following_controller()
        # This node's own locally-predicted (and now stale/wrong) block state.
        nc.engine.world_state.environment.destructible_blocks = [
            DestructibleBlock(x=100, y=200, destroyed=True)
        ]

        # The last authoritative snapshot received before the crash — the
        # real block was never actually destroyed.
        correct_env = EnvironmentalState(
            destructible_blocks=[DestructibleBlock(x=100, y=200, destroyed=False)]
        )
        nc.env_state_buffer.update(
            WorldStateSnapshot(
                sequence_number=42,
                world_state=WorldState(sequence_number=42, environment=correct_env),
            )
        )

        nc._on_reconnection_ack(
            ReconnectionAck(
                new_host_ip="10.0.0.2",
                udp_port=50010,
                game_events_port=50003,
                session_id="test-session",
            )
        )

        assert nc.engine.world_state.environment.destructible_blocks[0].destroyed is False

    def test_reconnection_ack_idempotent(self):
        """Second ack (relay echo) is ignored; roster stays consistent."""
        from distributed_smb.shared.messages.election import ReconnectionAck

        nc = self._make_following_controller()
        ack = ReconnectionAck(
            new_host_ip="10.0.0.2",
            udp_port=50010,
            game_events_port=50003,
            session_id="test-session",
        )
        nc._on_reconnection_ack(ack)
        nc._on_reconnection_ack(ack)  # second call must be a no-op

        assert nc.roster.get_player("player1") is None
        assert nc.roster.get_host().player_id == "player2"


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


# ---------------------------------------------------------------------------
# _merge_roster — peers that joined after this node built its own roster
# ---------------------------------------------------------------------------


class TestMergeRoster:
    def test_learning_a_late_joiner_prevents_a_sole_survivor_promotion(self):
        """Without the host's roster broadcast a node that rejoined mid-session
        is invisible to the peers already in game: on the next host crash each
        one sees no peers, promotes itself, and the session splits in two."""
        nc, _ = _make_controller()  # roster: player1 (host), player2 (self)
        assert nc._known_client_peers() == set()

        broadcast = GlobalRoster()
        broadcast.add_player(
            RosterEntry(
                player_id="player1",
                host="10.0.0.1",
                udp_port=HOST_UDP_PORT,
                join_index=0,
                is_host=True,
            )
        )
        broadcast.add_player(
            RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50011, join_index=1)
        )
        broadcast.add_player(
            RosterEntry(player_id="player4", host="10.0.0.4", udp_port=50013, join_index=3)
        )

        nc._merge_roster(broadcast)

        assert nc._known_client_peers() == {"10.0.0.4"}

    def test_merge_is_additive_and_idempotent(self):
        nc, _ = _make_controller()
        before = nc.roster.get_player("player1")

        broadcast = GlobalRoster()
        broadcast.add_player(
            RosterEntry(player_id="player4", host="10.0.0.4", udp_port=50013, join_index=3)
        )
        nc._merge_roster(broadcast)
        nc._merge_roster(broadcast)

        assert len(nc.roster.get_all_players()) == 3
        assert nc.roster.get_player("player1") == before
