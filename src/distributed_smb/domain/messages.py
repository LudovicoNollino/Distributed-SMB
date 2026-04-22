"""Data transfer objects exchanged between peers."""

from dataclasses import dataclass, field
from enum import StrEnum

from distributed_smb.domain.world import WorldState
from distributed_smb.shared.input import InputState


class MessageType(StrEnum):
    """Types of UDP packets exchanged during the M2 loopback milestone."""

    PLAYER_INPUT = "player_input"
    WORLD_STATE = "world_state"
    SESSION_CREATE = "session_create"
    SESSION_JOIN = "session_join"
    ROSTER_UPDATE = "roster_update"
    GAME_START = "game_start"
    INITIAL_STATE_SYNC = "initial_state_sync"


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

@dataclass(slots=True)
class SessionCreate:
    player_id: str
    message_type: MessageType = field(init=False, default=MessageType.SESSION_CREATE)

@dataclass(slots=True)
class SessionJoin:
    session_id: str
    player_id: str
    ip: str
    port: int
    message_type: MessageType = field(init=False, default=MessageType.SESSION_JOIN)

from distributed_smb.shared.roster import GlobalRoster

@dataclass(slots=True)
class RosterUpdate:
    roster: GlobalRoster
    message_type: MessageType = field(init=False, default=MessageType.ROSTER_UPDATE)

@dataclass(slots=True)
class GameStart:
    session_id: str
    message_type: MessageType = field(init=False, default=MessageType.GAME_START)

@dataclass(slots=True)
class InitialStateSync:
    world_state: WorldState
    message_type: MessageType = field(init=False, default=MessageType.INITIAL_STATE_SYNC)