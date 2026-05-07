from dataclasses import dataclass, field

from distributed_smb.shared.enums import MessageType
from distributed_smb.shared.messages.common import (
    MessageValidationError,
    validate_join_index,
    validate_player_id,
    validate_port,
)
from distributed_smb.shared.roster import GlobalRoster


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
