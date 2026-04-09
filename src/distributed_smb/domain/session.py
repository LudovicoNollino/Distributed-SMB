"""Session aggregate definitions."""

from dataclasses import dataclass, field

from distributed_smb.shared.enums import PlayerRole, SessionState


@dataclass(slots=True)
class GameSession:
    """Represents the lifecycle of a multiplayer match."""

    session_id: str
    host_player_id: str | None = None
    player_ids: list[str] = field(default_factory=list)
    state: SessionState = SessionState.WAITING
    local_role: PlayerRole = PlayerRole.CLIENT
