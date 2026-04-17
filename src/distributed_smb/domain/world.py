"""World state definitions."""

from dataclasses import dataclass, field

from distributed_smb.shared.config import PLAYER_HEIGHT, PLAYER_WIDTH


@dataclass(slots=True)
class CharacterState:
    """Minimal dynamic state for a controllable character."""

    player_id: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    width: int = PLAYER_WIDTH
    height: int = PLAYER_HEIGHT
    on_ground: bool = False


@dataclass(slots=True)
class WorldState:
    """Authoritative world snapshot stored locally."""

    sequence_number: int = 0
    characters: dict[str, CharacterState] = field(default_factory=dict)
