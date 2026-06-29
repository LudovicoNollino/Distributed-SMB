"""Integration tests for fault tolerance and host migration (M8).

These tests validate the full fault-tolerance chain:
  host crash → timeout detection → election → role promotion → reconnect → resume

Prerequisites (Persona 2):
  - ElectionMixin._promote_to_host() implemented in NodeController
  - game_event_broker.reconnect() / promote_to_server() wired
  - ReconnectionAck broadcast from new host to surviving clients

Until Persona 2 delivers, tests marked with @pytest.mark.skip are stubs
that define the acceptance criteria. Remove the skip decorator to activate.

Architecture note — why no explicit state transfer:
  Each client holds an up-to-date WorldState via the UDP snapshot stream.
  EnvironmentalStateBuffer keeps the last snapshot. On promotion, the new
  host calls bootstrap_from_snapshot(env_state_buffer.get_last()) and the
  world state is immediately authoritative — no extra protocol needed.
"""

import time

import pytest

from distributed_smb.application.election import (
    ElectionCoordinator,
    ElectionState,
    EnvironmentalStateBuffer,
    FollowingHost,
    HostTimeoutWatcher,
    SelfElected,
)
from distributed_smb.shared.config import (
    HOST_TIMEOUT_S,
    T_ELECTION_BASE_S,
    T_ELECTION_DELTA_S,
)
from distributed_smb.shared.messages.election import ReconnectionAck
from distributed_smb.shared.messages.sync import WorldStateSnapshot

# ---------------------------------------------------------------------------
# Unit-level integration: timeout watcher + election coordinator together
# ---------------------------------------------------------------------------


class TestTimeoutThenElection:
    """Verify the timeout → election handoff without any network."""

    def test_timeout_triggers_start_election(self):
        """Once timeout fires, start_election() should move coordinator to ELECTION_PENDING."""
        watcher = HostTimeoutWatcher(timeout_s=1.0)
        coordinator = ElectionCoordinator(
            join_index=0,
            my_ip="10.0.0.2",
            timeout_base_s=T_ELECTION_BASE_S,
            timeout_delta_s=T_ELECTION_DELTA_S,
        )
        t0 = time.time()
        watcher.reset(t0)

        assert not watcher.tick(t0 + 0.5)
        assert coordinator.state == ElectionState.IDLE

        assert watcher.tick(t0 + 1.001)
        coordinator.start_election({"10.0.0.3"})
        coordinator.set_election_timer(t0 + 1.001)
        assert coordinator.state == ElectionState.ELECTION_PENDING

    def test_coordinator_self_elects_after_timer(self):
        """After timeout and election start, the lowest-index node self-elects."""
        coordinator = ElectionCoordinator(
            join_index=0,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        t0 = time.time()
        coordinator.start_election(set())
        coordinator.set_election_timer(t0)

        event = coordinator.tick(t0 + 0.5)
        assert isinstance(event, SelfElected)
        assert event.my_ip == "10.0.0.2"

    def test_higher_index_yields_to_lower_claim(self):
        """Node with join_index=1 stops its election on receiving claim from join_index=0."""
        coordinator = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.3",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        t0 = time.time()
        coordinator.start_election({"10.0.0.2"})
        coordinator.set_election_timer(t0)

        event = coordinator.on_new_host_claim(claimer_join_index=0, claimer_ip="10.0.0.2")
        assert isinstance(event, FollowingHost)
        assert coordinator.state == ElectionState.FOLLOWER

        later_event = coordinator.tick(t0 + 1.0)
        assert later_event is None
        assert coordinator.state == ElectionState.FOLLOWER


class TestEnvironmentalStatePreservation:
    """Verify that the last snapshot is preserved through the buffer."""

    def _make_snapshot(self, seq: int, blocks_destroyed: bool = False):
        from unittest.mock import MagicMock

        ws = MagicMock()
        ws.sequence_number = seq
        ws.environment.destructible_blocks = [{"pos": (100, 100), "destroyed": blocks_destroyed}]
        snap = WorldStateSnapshot.__new__(WorldStateSnapshot)
        object.__setattr__(snap, "sequence_number", seq)
        object.__setattr__(snap, "world_state", ws)
        return snap

    def test_buffer_preserves_last_snapshot_before_crash(self):
        buf = EnvironmentalStateBuffer()
        for seq in range(1, 5):
            buf.update(self._make_snapshot(seq))
        last = buf.get_last()
        assert last.sequence_number == 4

    def test_buffer_with_destroyed_block(self):
        buf = EnvironmentalStateBuffer()
        buf.update(self._make_snapshot(1, blocks_destroyed=False))
        buf.update(self._make_snapshot(2, blocks_destroyed=True))
        last = buf.get_last()
        assert last.world_state.environment.destructible_blocks[0]["destroyed"] is True


class TestReconnectionAckValidation:
    """ReconnectionAck carries the data the client needs to resume."""

    def test_valid_reconnection_ack(self):
        ack = ReconnectionAck(
            new_host_ip="10.0.0.2",
            udp_port=50010,
            game_events_port=50003,
            session_id="test-session",
        )
        assert ack.new_host_ip == "10.0.0.2"
        assert ack.udp_port == 50010
        assert ack.game_events_port == 50003

    def test_reconnection_ack_serialization(self):
        from distributed_smb.network.serializer import Serializer

        serializer = Serializer()
        ack = ReconnectionAck(
            new_host_ip="10.0.0.2",
            udp_port=50010,
            game_events_port=50003,
            session_id="test-session",
        )
        encoded = serializer.encode_ws_message(ack)
        decoded = serializer.decode_ws_message(encoded)
        assert isinstance(decoded, ReconnectionAck)
        assert decoded.new_host_ip == "10.0.0.2"
        assert decoded.udp_port == 50010
        assert decoded.game_events_port == 50003
        assert decoded.session_id == "test-session"


# ---------------------------------------------------------------------------
# End-to-end process-level tests (require Persona 2 ElectionMixin)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires Persona 2 ElectionMixin + promote_to_host()")
class TestHostMigration3Players:
    """Kill the host process → session resumes on surviving client."""

    MIGRATION_TIMEOUT_S = HOST_TIMEOUT_S + T_ELECTION_BASE_S + 1.0

    def test_crash_and_resume(self):
        """One host + two clients on loopback. Kill host → session continues."""
        # TODO: spawn 1 host + 2 client subprocesses via subprocess.Popen
        # TODO: wait for lobby phase to complete (monitor logs or use IPC)
        # TODO: os.kill(host_proc.pid, signal.SIGKILL)
        # TODO: assert one of the two clients transitions to HOST within MIGRATION_TIMEOUT_S
        # TODO: assert the other client reconnects and resumes sending input packets
        raise NotImplementedError

    def test_environmental_state_preserved(self):
        """Block destroyed before crash is still destroyed after migration."""
        # TODO: spawn 1 host + 2 clients
        # TODO: trigger a block destruction event via WebSocket
        # TODO: kill host
        # TODO: after migration, query the new host's world state
        # TODO: assert the destroyed block is still marked destroyed
        raise NotImplementedError


@pytest.mark.skip(reason="Requires Persona 2 ElectionMixin + promote_to_host()")
class TestHostMigration4Players:
    """Same as 3-player test but with 3 clients."""

    def test_all_clients_reconnect(self):
        """Kill host with 3 clients → all 3 reconnect to new host."""
        # TODO: spawn 1 host + 3 client subprocesses
        # TODO: kill host
        # TODO: assert 1 client becomes host, 2 clients reconnect
        raise NotImplementedError


@pytest.mark.skip(reason="Requires Persona 2 ElectionMixin + promote_to_host()")
class TestCascadingFallback:
    """Crash of elected candidate triggers re-election of next candidate."""

    def test_primary_candidate_crash_elects_secondary(self):
        """JoinIndex=0 crashes during election → JoinIndex=1 becomes host."""
        # TODO: spawn 1 host (join_index=-1, the original) + 2 clients (join_index=0, 1)
        # TODO: kill original host to trigger election
        # TODO: before join_index=0 self-elects, kill its process too
        # TODO: assert join_index=1 eventually self-elects via cascading fallback
        raise NotImplementedError
