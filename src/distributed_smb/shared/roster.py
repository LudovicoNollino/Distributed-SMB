"""Distributed roster support structures."""

from dataclasses import dataclass, field

from distributed_smb.shared.enums import ConnectionStatus


@dataclass(slots=True)
class RosterEntry:
    """Represents a known participant in the session."""

    player_id: str
    host: str
    udp_port: int
    join_index: int
    status: ConnectionStatus = ConnectionStatus.CONNECTED


@dataclass(slots=True)
class GlobalRoster:
    """Locally replicated view of session participants."""

    entries: dict[str, RosterEntry] = field(default_factory=dict)
