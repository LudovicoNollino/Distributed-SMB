"""Election state machine: staggered timer-based distributed host election.

Implements deterministic host election via JoinIndex ordering and staggered delays.
This avoids voting rounds and achieves consensus without a central coordinator.

State transitions:
    IDLE -> ELECTION_PENDING (start_election triggered)
    ELECTION_PENDING -> CLAIMED (election timer expires, self-elected)
    ELECTION_PENDING -> FOLLOWER (valid NewHostClaim from lower-indexed peer received)
    CLAIMED -> FOLLOWER (NewHostClaim from lower-indexed peer overrides us)
    FOLLOWER -> ELECTION_PENDING (current_host unresponsive, cascade to next)
"""

from dataclasses import dataclass
from enum import Enum


class ElectionState(Enum):
    """State of the election process."""

    IDLE = "idle"
    """No election in progress; waiting for host timeout."""

    ELECTION_PENDING = "election_pending"
    """Election started; timer counting down before self-election."""

    CLAIMED = "claimed"
    """Self-elected as host; awaiting acknowledgment from peers."""

    FOLLOWER = "follower"
    """Following a host elected by another peer."""


@dataclass(slots=True)
class ElectionEvent:
    """Base class for election events emitted by ElectionCoordinator.tick()."""

    pass


@dataclass(slots=True)
class SelfElected(ElectionEvent):
    """Emitted when self-election timer expires without override from lower-indexed peer.

    Attributes:
        my_ip: IP address of the newly elected host (for network communication).
    """

    my_ip: str


@dataclass(slots=True)
class FollowingHost(ElectionEvent):
    """Emitted when a valid NewHostClaim received from lower-indexed peer.

    Attributes:
        claimer_ip: IP address of the elected host.
        claimer_join_index: JoinIndex of the elected host (for tie-breaking verification).
    """

    claimer_ip: str
    claimer_join_index: int


class ElectionCoordinator:
    """Staggered timer election coordinator.

    Deterministic host election:
    - Each node waits T = T_ELECTION_BASE_S + join_index * T_ELECTION_DELTA_S before self-electing.
    - Node with lowest JoinIndex wins (no conflicts in nominal case).
    - JoinIndex is assigned during lobby phase and never changes (stable total ordering).
    - If elected host becomes unresponsive, election cascades to next-lowest JoinIndex.

    Attributes:
        state: Current election state.
        join_index: 0-based node index (stable, assigned in lobby).
        my_ip: This node's IP address.
        current_host_ip: IP of currently elected host (when state == FOLLOWER).
        current_host_join_index: JoinIndex of currently elected host.
        known_peers: Set of peer IPs known to be alive (updated on cascade).
        election_timer_expiry: Unix timestamp when election timer fires (None if not pending).
    """

    def __init__(self, join_index: int, my_ip: str, timeout_base_s: float, timeout_delta_s: float):
        """Initialize the election coordinator.

        Args:
            join_index: 0-based position in the lobby join order (stable, permanent).
            my_ip: This node's IP address.
            timeout_base_s: T_ELECTION_BASE_S from config.
            timeout_delta_s: T_ELECTION_DELTA_S from config.
        """
        self.join_index = join_index
        self.my_ip = my_ip
        self.timeout_base_s = timeout_base_s
        self.timeout_delta_s = timeout_delta_s

        self.state = ElectionState.IDLE
        self.current_host_ip: str | None = None
        self.current_host_join_index: int | None = None
        self.known_peers: set[str] = set()
        self.election_timer_expiry: float | None = None

    def start_election(self, known_peers: set[str]) -> None:
        """Begin staggered election timer.

        Called when host timeout detected or cascading to next candidate.

        Args:
            known_peers: Set of peer IPs to broadcast NewHostClaim to.
        """
        self.state = ElectionState.ELECTION_PENDING
        self.known_peers = known_peers.copy()
        # Timer fires at: current_time + (T_ELECTION_BASE_S + join_index * T_ELECTION_DELTA_S)
        # Caller is responsible for setting election_timer_expiry before next tick().
        self.current_host_ip = None
        self.current_host_join_index = None

    def set_election_timer(self, current_time: float) -> None:
        """Set the election timer to fire after the staggered delay.

        Called after start_election() and before the main event loop tick.

        Args:
            current_time: Unix timestamp (typically time.time()).
        """
        delay = self.timeout_base_s + self.join_index * self.timeout_delta_s
        self.election_timer_expiry = current_time + delay

    def tick(self, current_time: float) -> ElectionEvent | None:
        """Process election state machine tick.

        Returns:
            SelfElected if election timer expires in ELECTION_PENDING state,
            None if no event triggered.

        Raises:
            ValueError if election_timer_expiry not set in ELECTION_PENDING state.
        """
        if self.state == ElectionState.ELECTION_PENDING:
            if self.election_timer_expiry is None:
                raise ValueError(
                    """election_timer_expiry must be set before calling tick()
                    in ELECTION_PENDING state"""
                )
            if current_time >= self.election_timer_expiry:
                self.state = ElectionState.CLAIMED
                return SelfElected(my_ip=self.my_ip)
        return None

    def on_new_host_claim(self, claimer_join_index: int, claimer_ip: str) -> ElectionEvent | None:
        """Process incoming NewHostClaim from a peer.

        Deterministic ordering: lower JoinIndex always wins. If we see a claim
        from a peer with lower JoinIndex:
        - We transition to FOLLOWER (we are not the elected host).
        - No further elections happen unless this host later times out.

        If we see a claim from peer with higher JoinIndex:
        - We ignore it (we are the rightful elected host).

        Args:
            claimer_join_index: JoinIndex of the claiming peer.
            claimer_ip: IP address of the claiming peer.

        Returns:
            FollowingHost if we transition to FOLLOWER (accept the claim),
            None if we reject or ignore the claim.
        """
        if claimer_join_index >= self.join_index:
            # Claimer has higher or equal JoinIndex: we are the rightful host, ignore.
            return None

        # Claimer has lower JoinIndex: they win.
        self.state = ElectionState.FOLLOWER
        self.current_host_ip = claimer_ip
        self.current_host_join_index = claimer_join_index
        self.election_timer_expiry = None
        return FollowingHost(claimer_ip=claimer_ip, claimer_join_index=claimer_join_index)

    def on_claim_unresponsive(self, failed_ip: str) -> None:
        """Current elected host became unresponsive.

        Cascade: remove failed_ip from known_peers and restart election
        with the updated peer set. The next lowest-JoinIndex node will
        eventually elect itself.

        Args:
            failed_ip: IP address of the unresponsive host.
        """
        if failed_ip in self.known_peers:
            self.known_peers.discard(failed_ip)
        # Cascade: restart election with updated known_peers
        self.start_election(self.known_peers)

    def get_state_info(self) -> dict:
        """Return current state for debugging/logging.

        Returns:
            Dict with state, join_index, current_host_ip, election_timer_expiry.
        """
        return {
            "state": self.state.value,
            "join_index": self.join_index,
            "my_ip": self.my_ip,
            "current_host_ip": self.current_host_ip,
            "current_host_join_index": self.current_host_join_index,
            "election_timer_expiry": self.election_timer_expiry,
        }
