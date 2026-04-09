"""Player model definitions."""

from dataclasses import dataclass

from distributed_smb.shared.enums import ConnectionStatus, PlayerRole


@dataclass(slots=True)
class Player:
    """Represents a participant in a session."""

    player_id: str
    username: str
    role: PlayerRole = PlayerRole.CLIENT
    connection_status: ConnectionStatus = ConnectionStatus.CONNECTED
    join_index: int = 0
