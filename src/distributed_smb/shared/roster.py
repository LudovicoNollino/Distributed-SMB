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
    isHost: bool = False


@dataclass(slots=True)
class GlobalRoster:
    """Locally replicated view of session participants."""

    players: list[RosterEntry] = field(default_factory=list)

    def add_player(self, entry: RosterEntry):
        self.players.append(entry)

    def get_player(self, player_id: str) -> RosterEntry | None:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None
