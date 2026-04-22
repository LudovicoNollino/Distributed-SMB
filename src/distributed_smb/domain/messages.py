"""Data transfer objects exchanged between peers."""

from dataclasses import dataclass, field
from enum import StrEnum

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
    player_id: str
    message_type: MessageType = field(init=False, default=MessageType.SESSION_CREATE)

    def __post_init__(self):
        validate_player_id(self.player_id)


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
