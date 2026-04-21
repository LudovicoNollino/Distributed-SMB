"""Data transfer objects exchanged between peers."""

from dataclasses import dataclass, field
from enum import StrEnum

from distributed_smb.domain.world import WorldState
from distributed_smb.shared.input import InputState


class MessageType(StrEnum):
    """Types of UDP packets exchanged during the M2 loopback milestone."""

    PLAYER_INPUT = "player_input"
    WORLD_STATE = "world_state"


@dataclass(slots=True)
class PlayerInputPacket:
    """Represents an input packet sent by a client to the host."""

    player_id: str
    sequence_number: int
    input_state: InputState = field(default_factory=InputState)
    message_type: MessageType = field(init=False, default=MessageType.PLAYER_INPUT)


@dataclass(slots=True)
class WorldStateSnapshot:
    """Represents a world snapshot sent by the authoritative host."""

    sequence_number: int
    world_state: WorldState = field(default_factory=WorldState)
    message_type: MessageType = field(init=False, default=MessageType.WORLD_STATE)
