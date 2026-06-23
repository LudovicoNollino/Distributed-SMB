"""Election and host migration messages.

WebSocket peer-to-peer messages broadcast to all known peers during host election.
"""

from dataclasses import dataclass, field

from distributed_smb.shared.enums import MessageType
from distributed_smb.shared.messages.common import MessageValidationError


@dataclass(slots=True)
class NewHostClaim:
    """Broadcast peer-to-peer: node claims to be the new host.

    Sent when a node's election timer expires (or cascades to it after previous
    host became unresponsive). All peers receive this claim and transition to FOLLOWER state.

    Attributes:
        claimer_ip: IP address of the node claiming to be host.
        claimer_join_index: JoinIndex of the claimer (for deterministic ordering verification).
        session_id: Session ID to prevent cross-session claim confusion.
        message_type: MessageType.NEW_HOST_CLAIM.
    """

    claimer_ip: str
    claimer_join_index: int
    session_id: str
    message_type: MessageType = field(init=False, default=MessageType.NEW_HOST_CLAIM)

    def __post_init__(self):
        if not self.claimer_ip or not isinstance(self.claimer_ip, str):
            raise MessageValidationError(f"Invalid claimer_ip: {self.claimer_ip}")
        if self.claimer_join_index < 0:
            raise MessageValidationError(f"Invalid claimer_join_index: {self.claimer_join_index}")
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")


@dataclass(slots=True)
class ElectionAck:
    """Unicast reply to NewHostClaim: peer acknowledges the claim.

    Sent by peers in response to NewHostClaim to confirm they received and accepted
    the host election. Claimer uses these ACKs to verify quorum and confirm host election.

    Attributes:
        from_ip: IP address of the peer sending this ACK.
        session_id: Session ID to match against the NewHostClaim.
        message_type: MessageType.ELECTION_ACK.
    """

    from_ip: str
    session_id: str
    message_type: MessageType = field(init=False, default=MessageType.ELECTION_ACK)

    def __post_init__(self):
        if not self.from_ip or not isinstance(self.from_ip, str):
            raise MessageValidationError(f"Invalid from_ip: {self.from_ip}")
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")


@dataclass(slots=True)
class ElectionNack:
    """Unicast reply to NewHostClaim: peer rejects the claim.

    Sent if the claimer is not the node with the lowest JoinIndex (race condition).
    Causes the claimer to revert to FOLLOWER state and not claim hostship.

    Attributes:
        from_ip: IP address of the peer sending this NACK.
        session_id: Session ID to match against the NewHostClaim.
        reason: Human-readable reason for rejection (e.g., "lower_join_index_available").
        message_type: MessageType.ELECTION_NACK.
    """

    from_ip: str
    session_id: str
    reason: str
    message_type: MessageType = field(init=False, default=MessageType.ELECTION_NACK)

    def __post_init__(self):
        if not self.from_ip or not isinstance(self.from_ip, str):
            raise MessageValidationError(f"Invalid from_ip: {self.from_ip}")
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")
        if not self.reason or not isinstance(self.reason, str):
            raise MessageValidationError(f"Invalid reason: {self.reason}")
