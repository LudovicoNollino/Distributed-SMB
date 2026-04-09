"""Data transfer objects exchanged between peers."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlayerInputMessage:
    """Represents an input packet sent by a client."""

    player_id: str
    sequence_number: int
    pressed_actions: set[str] = field(default_factory=set)


@dataclass(slots=True)
class WorldStateMessage:
    """Represents a world snapshot sent by the authoritative host."""

    sequence_number: int
    payload: dict[str, object] = field(default_factory=dict)
