"""Unit tests for failure detection and host election algorithms.

Tests cover:
- HostTimeoutWatcher: timeout-based failure detection
- ElectionCoordinator: staggered timer election with deterministic ordering
"""

import time

import pytest

from distributed_smb.application.election import (
    ElectionCoordinator,
    ElectionState,
    FollowingHost,
    HostTimeoutWatcher,
    SelfElected,
)
from distributed_smb.shared.config import (
    T_ELECTION_BASE_S,
    T_ELECTION_DELTA_S,
)


class TestHostTimeoutWatcher:
    """HostTimeoutWatcher: eventually perfect failure detector via timeout."""

    def test_no_timeout_before_first_snapshot(self):
        """Watcher returns False until first snapshot received."""
        watcher = HostTimeoutWatcher(timeout_s=5.0)
        current_time = time.time()
        assert watcher.tick(current_time) is False

    def test_no_timeout_within_interval(self):
        """Watcher returns False while snapshot is recent."""
        watcher = HostTimeoutWatcher(timeout_s=5.0)
        t0 = time.time()
        watcher.reset(t0)
        # Within timeout interval
        assert watcher.tick(t0 + 2.0) is False
        assert watcher.tick(t0 + 4.9) is False

    def test_timeout_after_interval(self):
        """Watcher returns True once timeout_s exceeded."""
        watcher = HostTimeoutWatcher(timeout_s=5.0)
        t0 = time.time()
        watcher.reset(t0)
        # Just at boundary
        assert watcher.tick(t0 + 5.0) is False
        # Just past boundary
        assert watcher.tick(t0 + 5.001) is True

    def test_reset_clears_timeout(self):
        """Watcher resets on new snapshot."""
        watcher = HostTimeoutWatcher(timeout_s=5.0)
        t0 = time.time()
        watcher.reset(t0)
        # Time advances, snapshot times out
        assert watcher.tick(t0 + 5.5) is True
        # Reset with new snapshot
        watcher.reset(t0 + 5.5)
        # Now within new interval
        assert watcher.tick(t0 + 8.0) is False


class TestElectionCoordinatorBasics:
    """ElectionCoordinator: deterministic election via JoinIndex ordering."""

    def test_initial_state_is_idle(self):
        """Coordinator starts in IDLE state."""
        coordinator = ElectionCoordinator(
            join_index=0,
            my_ip="127.0.0.1",
            timeout_base_s=T_ELECTION_BASE_S,
            timeout_delta_s=T_ELECTION_DELTA_S,
        )
        assert coordinator.state == ElectionState.IDLE

    def test_start_election_transitions_to_pending(self):
        """start_election() moves to ELECTION_PENDING."""
        coordinator = ElectionCoordinator(
            join_index=0,
            my_ip="127.0.0.1",
            timeout_base_s=T_ELECTION_BASE_S,
            timeout_delta_s=T_ELECTION_DELTA_S,
        )
        coordinator.start_election({"127.0.0.2", "127.0.0.3"})
        assert coordinator.state == ElectionState.ELECTION_PENDING
        assert coordinator.known_peers == {"127.0.0.2", "127.0.0.3"}

    def test_election_timer_calculation(self):
        """set_election_timer() calculates T = T_BASE + join_index * T_DELTA."""
        coordinator = ElectionCoordinator(
            join_index=2,
            my_ip="127.0.0.1",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        t0 = 1000.0
        coordinator.start_election(set())
        coordinator.set_election_timer(t0)
        # T = 0.5 + 2 * 0.3 = 1.1
        expected_expiry = t0 + 1.1
        assert coordinator.election_timer_expiry == pytest.approx(expected_expiry)

    def test_tick_self_elected_when_timer_fires(self):
        """tick() returns SelfElected when timer expires in ELECTION_PENDING."""
        coordinator = ElectionCoordinator(
            join_index=0,
            my_ip="192.168.1.1",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        t0 = 1000.0
        coordinator.start_election(set())
        coordinator.set_election_timer(t0)
        # Timer not yet expired
        event = coordinator.tick(t0 + 0.49)
        assert event is None
        # Timer fired
        event = coordinator.tick(t0 + 0.5)
        assert isinstance(event, SelfElected)
        assert event.my_ip == "192.168.1.1"
        assert coordinator.state == ElectionState.CLAIMED

    def test_lower_join_index_wins(self):
        """Node with lower JoinIndex wins election (deterministic ordering)."""
        # Node A: join_index=0
        a = ElectionCoordinator(
            join_index=0, my_ip="10.0.0.1", timeout_base_s=0.5, timeout_delta_s=0.3
        )
        # Node B: join_index=1
        b = ElectionCoordinator(
            join_index=1, my_ip="10.0.0.2", timeout_base_s=0.5, timeout_delta_s=0.3
        )
        # Both start election at same time
        t0 = 1000.0
        a.start_election({"10.0.0.2"})
        a.set_election_timer(t0)
        b.start_election({"10.0.0.1"})
        b.set_election_timer(t0)
        # A's timer: 0.5 + 0 * 0.3 = 0.5
        # B's timer: 0.5 + 1 * 0.3 = 0.8
        # A fires first
        event_a = a.tick(t0 + 0.5)
        assert isinstance(event_a, SelfElected)
        assert a.state == ElectionState.CLAIMED
        # B fires later
        event_b = b.tick(t0 + 0.5)
        assert event_b is None
        assert b.state == ElectionState.ELECTION_PENDING


class TestElectionCoordinatorClaiming:
    """ElectionCoordinator: handling NewHostClaim messages."""

    def test_accept_claim_from_lower_join_index(self):
        """Node accepts NewHostClaim from lower-indexed peer."""
        # Node at join_index=2 receives claim from join_index=0
        node = ElectionCoordinator(
            join_index=2,
            my_ip="10.0.0.3",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        node.start_election({"10.0.0.1", "10.0.0.2"})
        event = node.on_new_host_claim(claimer_join_index=0, claimer_ip="10.0.0.1")
        assert isinstance(event, FollowingHost)
        assert event.claimer_ip == "10.0.0.1"
        assert event.claimer_join_index == 0
        assert node.state == ElectionState.FOLLOWER
        assert node.current_host_ip == "10.0.0.1"

    def test_reject_claim_from_higher_join_index(self):
        """Node rejects NewHostClaim from higher-indexed peer (we are rightful host)."""
        # Node at join_index=1 receives claim from join_index=2
        node = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        node.state = ElectionState.CLAIMED
        event = node.on_new_host_claim(claimer_join_index=2, claimer_ip="10.0.0.3")
        assert event is None
        assert node.state == ElectionState.CLAIMED  # No state change

    def test_claim_overrides_claimed_state(self):
        """Node transitions from CLAIMED to FOLLOWER if better candidate appears."""
        node = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        node.state = ElectionState.CLAIMED
        node.current_host_join_index = 1
        # Better candidate (join_index=0) arrives
        event = node.on_new_host_claim(claimer_join_index=0, claimer_ip="10.0.0.1")
        assert isinstance(event, FollowingHost)
        assert node.state == ElectionState.FOLLOWER
        assert node.current_host_ip == "10.0.0.1"


class TestElectionCoordinatorCascade:
    """ElectionCoordinator: cascading fallback on host failure."""

    def test_cascade_on_unresponsive_host(self):
        """on_claim_unresponsive() triggers cascade: restart election."""
        # Node at join_index=2, following join_index=0
        node = ElectionCoordinator(
            join_index=2,
            my_ip="10.0.0.3",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        node.state = ElectionState.FOLLOWER
        node.current_host_ip = "10.0.0.1"
        node.current_host_join_index = 0
        peers = {"10.0.0.1", "10.0.0.2"}
        node.known_peers = peers.copy()
        # Host becomes unresponsive
        node.on_claim_unresponsive("10.0.0.1")
        # Cascade: back to ELECTION_PENDING, peer removed from known_peers
        assert node.state == ElectionState.ELECTION_PENDING
        assert "10.0.0.1" not in node.known_peers
        assert node.current_host_ip is None

    def test_cascade_eventually_elects_next_candidate(self):
        """After cascading, next-lowest JoinIndex eventually self-elects."""
        # Simulate join_index=0 and join_index=1 in the system
        # join_index=1 is following join_index=0
        follower = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        follower.state = ElectionState.FOLLOWER
        follower.current_host_ip = "10.0.0.1"
        follower.current_host_join_index = 0
        follower.known_peers = {"10.0.0.1"}
        # Host 10.0.0.1 becomes unresponsive
        follower.on_claim_unresponsive("10.0.0.1")
        assert follower.state == ElectionState.ELECTION_PENDING
        # Set timer and let it fire
        t0 = 1000.0
        follower.set_election_timer(t0)
        # Timer for join_index=1: 0.5 + 1 * 0.3 = 0.8
        event = follower.tick(t0 + 0.8)
        assert isinstance(event, SelfElected)
        assert event.my_ip == "10.0.0.2"


class TestElectionCoordinatorNoDoublElection:
    """ElectionCoordinator: prevent double elections and race conditions."""

    def test_no_election_double_when_claim_received_early(self):
        """Receiving valid claim before timer fires prevents self-election."""
        coordinator = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        t0 = 1000.0
        coordinator.start_election({"10.0.0.1"})
        coordinator.set_election_timer(t0)
        # Claim arrives from lower-indexed node BEFORE timer fires
        event = coordinator.on_new_host_claim(claimer_join_index=0, claimer_ip="10.0.0.1")
        assert isinstance(event, FollowingHost)
        assert coordinator.state == ElectionState.FOLLOWER
        # Timer still hasn't fired, but we're already in FOLLOWER state
        # Tick past the timer expiry time, should return None (no state change)
        event = coordinator.tick(t0 + 0.8)
        assert event is None
        assert coordinator.state == ElectionState.FOLLOWER


class TestElectionCoordinatorStateInfo:
    """ElectionCoordinator: debugging and introspection."""

    def test_get_state_info(self):
        """get_state_info() returns current state snapshot."""
        coordinator = ElectionCoordinator(
            join_index=1,
            my_ip="10.0.0.2",
            timeout_base_s=0.5,
            timeout_delta_s=0.3,
        )
        info = coordinator.get_state_info()
        assert info["state"] == "idle"
        assert info["join_index"] == 1
        assert info["my_ip"] == "10.0.0.2"
        assert info["current_host_ip"] is None
        # After state change
        coordinator.start_election(set())
        info = coordinator.get_state_info()
        assert info["state"] == "election_pending"
