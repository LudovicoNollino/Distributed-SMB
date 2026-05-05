"""Data transfer objects exchanged between peers."""

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

from distributed_smb.domain.world import WorldState
from distributed_smb.shared.input import InputState
from distributed_smb.shared.roster import GlobalRoster


class MessageValidationError(ValueError):
    """Raised when a message fails validation."""

    pass


def validate_player_id(player_id: str) -> None:
    """Validate that player_id is non-empty string."""
    if not player_id or not isinstance(player_id, str):
        raise MessageValidationError(f"Invalid player_id: {player_id}")


def validate_port(port: int) -> None:
    """Validate that port is in valid range."""
    if not (1024 <= port <= 65535):
        raise MessageValidationError(f"Port out of range: {port}")


def validate_join_index(join_index: int) -> None:
    """Validate that join_index is non-negative."""
    if join_index < 0:
        raise MessageValidationError(f"join_index must be >= 0, got {join_index}")


class MessageType(StrEnum):
    """Message types exchanged over UDP (gameplay) and WebSocket (coordination)."""

    # UDP — high-frequency gameplay
    PLAYER_INPUT = "player_input"
    WORLD_STATE = "world_state"

    # WebSocket — lobby coordination (client → lobby)
    SESSION_CREATE = "session_create"
    SESSION_JOIN = "session_join"
    GAME_START = "game_start"
    INITIAL_STATE_SYNC = "initial_state_sync"

    # WebSocket — lobby coordination (lobby → client)
    SESSION_CREATED = "session_created"
    SESSION_JOINED = "session_joined"
    ROSTER_UPDATE = "roster_update"

    BLOCK_DESTROYED_EVENT = "block_destroyed_event"
    POWERUP_COLLECTED_EVENT = "powerup_collected_event"
    GATE_STATE_CHANGED_EVENT = "gate_state_changed_event"
    PLAYER_LEFT = "player_left"
    PLAYER_DISCONNECTED = "player_disconnected"


@dataclass(slots=True)
class PlayerInputPacket:
    """Represents an input packet sent by a client to the host."""

    player_id: str
    sequence_number: int
    input_state: InputState = field(default_factory=InputState)
    message_type: MessageType = field(init=False, default=MessageType.PLAYER_INPUT)

    def __post_init__(self):
        validate_player_id(self.player_id)


@dataclass(slots=True)
class WorldStateSnapshot:
    """Represents a world snapshot sent by the authoritative host."""

    sequence_number: int
    world_state: WorldState = field(default_factory=WorldState)
    message_type: MessageType = field(init=False, default=MessageType.WORLD_STATE)


@dataclass(slots=True)
class SessionCreate:
    """Sent by the host to the lobby to create a new session."""

    player_id: str
    ip: str
    udp_port: int
    message_type: MessageType = field(init=False, default=MessageType.SESSION_CREATE)

    def __post_init__(self):
        validate_player_id(self.player_id)
        validate_port(self.udp_port)
        if not self.ip or not isinstance(self.ip, str):
            raise MessageValidationError(f"Invalid ip: {self.ip}")


@dataclass(slots=True)
class SessionJoin:
    session_id: str
    player_id: str
    ip: str
    port: int
    message_type: MessageType = field(init=False, default=MessageType.SESSION_JOIN)

    def __post_init__(self):
        validate_player_id(self.player_id)
        validate_port(self.port)
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")
        if not self.ip or not isinstance(self.ip, str):
            raise MessageValidationError(f"Invalid ip: {self.ip}")


@dataclass(slots=True)
class SessionCreated:
    """Sent by the lobby to the host after a session is created successfully."""

    session_id: str
    join_index: int
    message_type: MessageType = field(init=False, default=MessageType.SESSION_CREATED)

    def __post_init__(self):
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")
        validate_join_index(self.join_index)


@dataclass(slots=True)
class SessionJoined:
    """Sent by the lobby to the joining client after a successful join."""

    join_index: int
    message_type: MessageType = field(init=False, default=MessageType.SESSION_JOINED)

    def __post_init__(self):
        validate_join_index(self.join_index)


@dataclass(slots=True)
class RosterUpdate:
    roster: GlobalRoster
    message_type: MessageType = field(init=False, default=MessageType.ROSTER_UPDATE)

    def __post_init__(self):
        # Validate that all roster entries have unique join indices
        join_indices = [entry.join_index for entry in self.roster.players]
        if len(join_indices) != len(set(join_indices)):
            raise MessageValidationError("Roster has duplicate join_index values")


@dataclass(slots=True)
class GameStart:
    session_id: str
    message_type: MessageType = field(init=False, default=MessageType.GAME_START)

    def __post_init__(self):
        if not self.session_id or not isinstance(self.session_id, str):
            raise MessageValidationError(f"Invalid session_id: {self.session_id}")


@dataclass(slots=True)
class InitialStateSync:
    world_state: WorldState
    message_type: MessageType = field(init=False, default=MessageType.INITIAL_STATE_SYNC)

@dataclass(slots=True)
class BlockDestroyedEvent:
    position: tuple[int, int]
    message_type: MessageType = field(init=False, default=MessageType.BLOCK_DESTROYED_EVENT)

    def __post_init__(self):
        if (
            not isinstance(self.position, tuple)
            or len(self.position) != 2
            or not all(isinstance(coord, int) for coord in self.position)
        ):
            raise MessageValidationError(f"Invalid position: {self.position}")


@dataclass(slots=True)
class PowerUpCollectedEvent:
    powerup_id: str
    player_id: str
    message_type: MessageType = field(init=False, default=MessageType.POWERUP_COLLECTED_EVENT)

    def __post_init__(self):
        if not self.powerup_id or not isinstance(self.powerup_id, str):
            raise MessageValidationError(f"Invalid powerup_id: {self.powerup_id}")
        validate_player_id(self.player_id)


@dataclass(slots=True)
class GateStateChangedEvent:
    gate_id: str
    new_state: str
    message_type: MessageType = field(init=False, default=MessageType.GATE_STATE_CHANGED_EVENT)

    def __post_init__(self):
        if not self.gate_id or not isinstance(self.gate_id, str):
            raise MessageValidationError(f"Invalid gate_id: {self.gate_id}")
        if not self.new_state or not isinstance(self.new_state, str):
            raise MessageValidationError(f"Invalid new_state: {self.new_state}")


@dataclass(slots=True)
class PlayerLeft:
    player_id: str
    message_type: MessageType = field(init=False, default=MessageType.PLAYER_LEFT)

    def __post_init__(self):
        validate_player_id(self.player_id)


@dataclass(slots=True)
class PlayerDisconnected:
    player_id: str
    message_type: MessageType = field(init=False, default=MessageType.PLAYER_DISCONNECTED)

    def __post_init__(self):
        validate_player_id(self.player_id)

class PlayerInputSchema(BaseModel):
    """Schema for UDP PlayerInputPacket validation."""

    player_id: str = Field(..., min_length=1)
    sequence_number: int = Field(...)
    input_state: dict = Field(default_factory=dict)
    message_type: str = Field(default="player_input")


class WorldStateSchema(BaseModel):
    """Schema for UDP WorldStateSnapshot validation."""

    sequence_number: int = Field(...)
    world_state: dict = Field(...)
    message_type: str = Field(default="world_state")


class SessionCreateSchema(BaseModel):
    """Schema for WebSocket SessionCreate message."""

    player_id: str = Field(..., min_length=1)
    ip: str = Field(..., min_length=1)
    udp_port: int = Field(..., ge=1024, le=65535)
    message_type: str = Field(default="session_create")


class SessionJoinSchema(BaseModel):
    """Schema for WebSocket SessionJoin message."""

    session_id: str = Field(..., min_length=1)
    player_id: str = Field(..., min_length=1)
    ip: str = Field(..., min_length=1)
    port: int = Field(..., ge=1024, le=65535)
    message_type: str = Field(default="session_join")


class SessionCreatedSchema(BaseModel):
    """Schema for WebSocket SessionCreated message."""

    session_id: str = Field(..., min_length=1)
    join_index: int = Field(..., ge=0)
    message_type: str = Field(default="session_created")


class SessionJoinedSchema(BaseModel):
    """Schema for WebSocket SessionJoined message."""

    join_index: int = Field(..., ge=0)
    message_type: str = Field(default="session_joined")


class RosterEntrySchema(BaseModel):
    """Schema for roster entry validation."""

    player_id: str = Field(..., min_length=1)
    host: str = Field(..., min_length=1)
    udp_port: int = Field(..., ge=1024, le=65535)
    join_index: int = Field(..., ge=0)
    status: str = Field(...)
    is_host: bool = Field(...)


class RosterSchema(BaseModel):
    """Schema for roster."""

    players: list[RosterEntrySchema] = Field(...)


class RosterUpdateSchema(BaseModel):
    """Schema for WebSocket RosterUpdate message."""

    roster: RosterSchema = Field(...)
    message_type: str = Field(default="roster_update")


class GameStartSchema(BaseModel):
    """Schema for WebSocket GameStart message."""

    session_id: str = Field(..., min_length=1)
    message_type: str = Field(default="game_start")


class InitialStateSyncSchema(BaseModel):
    """Schema for WebSocket InitialStateSync message."""

    world_state: dict = Field(...)
    message_type: str = Field(default="initial_state_sync")

class BlockDestroyedEventSchema(BaseModel):
    position: list[int] = Field(..., min_items=2, max_items=2)
    message_type: str = Field(default="block_destroyed_event")


class PowerUpCollectedEventSchema(BaseModel):
    powerup_id: str = Field(..., min_length=1)
    player_id: str = Field(..., min_length=1)
    message_type: str = Field(default="powerup_collected_event")


class GateStateChangedEventSchema(BaseModel):
    gate_id: str = Field(..., min_length=1)
    new_state: str = Field(..., min_length=1)
    message_type: str = Field(default="gate_state_changed_event")


class PlayerLeftSchema(BaseModel):
    player_id: str = Field(..., min_length=1)
    message_type: str = Field(default="player_left")


class PlayerDisconnectedSchema(BaseModel):
    player_id: str = Field(..., min_length=1)
    message_type: str = Field(default="player_disconnected")
