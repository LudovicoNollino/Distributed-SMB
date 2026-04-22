"""Session aggregate definitions."""

from dataclasses import dataclass, field

from distributed_smb.shared.enums import PlayerRole, SessionState
from distributed_smb.shared.roster import GlobalRoster


@dataclass(slots=True)
class GameSession:
    """Represents the lifecycle of a multiplayer match."""

    session_id: str
    host_player_id: str | None = None
    roster: GlobalRoster = field(default_factory=GlobalRoster)
    state: SessionState = SessionState.WAITING
    local_role: PlayerRole = PlayerRole.CLIENT
