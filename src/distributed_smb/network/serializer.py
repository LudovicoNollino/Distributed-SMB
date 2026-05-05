"""Message serialization helpers."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Union

from pydantic import ValidationError

from distributed_smb.domain.messages import (
    BlockDestroyedEvent,
    BlockDestroyedEventSchema,
    GameStart,
    GameStartSchema,
    GateStateChangedEvent,
    GateStateChangedEventSchema,
    InitialStateSync,
    InitialStateSyncSchema,
    MessageType,
    PlayerDisconnected,
    PlayerDisconnectedSchema,
    PlayerInputPacket,
    PlayerInputSchema,
    PlayerLeft,
    PlayerLeftSchema,
    PowerUpCollectedEvent,
    PowerUpCollectedEventSchema,
    RosterUpdate,
    RosterUpdateSchema,
    SessionCreate,
    SessionCreated,
    SessionCreatedSchema,
    SessionCreateSchema,
    SessionJoin,
    SessionJoined,
    SessionJoinedSchema,
    SessionJoinSchema,
    WorldStateSchema,
    WorldStateSnapshot,
)

from distributed_smb.domain.entity import CooperativeGate, DestructibleBlock, ExclusivePowerUp
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.enums import ConnectionStatus
from distributed_smb.shared.input import InputState
from distributed_smb.shared.roster import GlobalRoster, RosterEntry

# Union type for all WebSocket coordination messages
WsMessage = Union[
    SessionCreate,
    SessionCreated,
    SessionJoin,
    SessionJoined,
    RosterUpdate,
    GameStart,
    InitialStateSync,
    BlockDestroyedEvent,
    PowerUpCollectedEvent,
    GateStateChangedEvent,
    PlayerLeft,
    PlayerDisconnected,
]


class DeserializationError(ValueError):
    """Raised when deserialization fails."""

    pass


class Serializer:
    """Serialize basic Python objects and dataclasses to JSON."""

    def encode(self, payload: object) -> str:
        """Encode the given payload to JSON."""
        if is_dataclass(payload):
            payload = asdict(payload)
        return json.dumps(payload)

    def decode(self, payload: str | bytes) -> Any:
        """Decode JSON data into a Python object."""
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)

    # ------------------------------------------------------------------
    # UDP transport
    # ------------------------------------------------------------------

    def encode_message(self, payload: PlayerInputPacket | WorldStateSnapshot) -> bytes:
        """Encode a gameplay packet to bytes ready for UDP transport."""
        return self.encode(payload).encode("utf-8")

    def decode_message(self, payload: str | bytes) -> PlayerInputPacket | WorldStateSnapshot:
        """Decode a UDP gameplay packet into its typed dataclass."""
        data = self.decode(payload)
        message_type = data.get("message_type")

        try:
            if message_type == MessageType.PLAYER_INPUT:
                validated = PlayerInputSchema(**data)
                return PlayerInputPacket(
                    player_id=validated.player_id,
                    sequence_number=validated.sequence_number,
                    input_state=InputState(**validated.input_state),
                )

            if message_type == MessageType.WORLD_STATE:
                validated = WorldStateSchema(**data)
                characters = {
                    player_id: CharacterState(**character_data)
                    for player_id, character_data in validated.world_state["characters"].items()
                }
                world_state = WorldState(
                    sequence_number=validated.world_state["sequence_number"],
                    characters=characters,
                )
                return WorldStateSnapshot(
                    sequence_number=validated.sequence_number,
                    world_state=world_state,
                )

            raise DeserializationError(f"Unsupported UDP message type: {message_type}")

        except ValidationError as e:
            raise DeserializationError(f"Invalid UDP message format: {e.errors()}")

    # ------------------------------------------------------------------
    # WebSocket transport
    # ------------------------------------------------------------------

    def encode_ws_message(self, payload: WsMessage) -> dict:
        """Encode a lobby coordination message to a JSON-compatible dict.

        The returned dict is sent as-is over the WebSocket connection; the
        WebSocket layer is responsible for calling json.dumps on it.
        """
        return asdict(payload)

    def decode_ws_message(self, data: dict) -> WsMessage:
        """Decode a dict received from a WebSocket into a typed message."""
        message_type = data.get("message_type")

        try:
            if message_type == MessageType.SESSION_CREATE:
                validated = SessionCreateSchema(**data)
                return SessionCreate(
                    player_id=validated.player_id,
                    ip=validated.ip,
                    udp_port=validated.udp_port,
                )

            if message_type == MessageType.SESSION_CREATED:
                validated = SessionCreatedSchema(**data)
                return SessionCreated(
                    session_id=validated.session_id,
                    join_index=validated.join_index,
                )

            if message_type == MessageType.SESSION_JOIN:
                validated = SessionJoinSchema(**data)
                return SessionJoin(
                    session_id=validated.session_id,
                    player_id=validated.player_id,
                    ip=validated.ip,
                    port=validated.port,
                )

            if message_type == MessageType.SESSION_JOINED:
                validated = SessionJoinedSchema(**data)
                return SessionJoined(join_index=validated.join_index)

            if message_type == MessageType.ROSTER_UPDATE:
                validated = RosterUpdateSchema(**data)
                roster = GlobalRoster()
                for entry_data in validated.roster.players:
                    roster.add_player(
                        RosterEntry(
                            player_id=entry_data.player_id,
                            host=entry_data.host,
                            udp_port=entry_data.udp_port,
                            join_index=entry_data.join_index,
                            status=ConnectionStatus(entry_data.status),
                            is_host=entry_data.is_host,
                        )
                    )
                return RosterUpdate(roster=roster)

            if message_type == MessageType.GAME_START:
                validated = GameStartSchema(**data)
                return GameStart(session_id=validated.session_id)

            if message_type == MessageType.INITIAL_STATE_SYNC:
                validated = InitialStateSyncSchema(**data)
                characters = {
                    pid: CharacterState(**cs)
                    for pid, cs in validated.world_state["characters"].items()
                }
                world_state = WorldState(
                    sequence_number=validated.world_state["sequence_number"],
                    characters=characters,
                )
                return InitialStateSync(world_state=world_state)

            if message_type == MessageType.BLOCK_DESTROYED_EVENT:
                validated = BlockDestroyedEventSchema(**data)
                return BlockDestroyedEvent(position=tuple(validated.position))

            if message_type == MessageType.POWERUP_COLLECTED_EVENT:
                validated = PowerUpCollectedEventSchema(**data)
                return PowerUpCollectedEvent(
                    powerup_id=validated.powerup_id,
                    player_id=validated.player_id,
                )

            if message_type == MessageType.GATE_STATE_CHANGED_EVENT:
                validated = GateStateChangedEventSchema(**data)
                return GateStateChangedEvent(
                    gate_id=validated.gate_id,
                    new_state=validated.new_state,
                )

            if message_type == MessageType.PLAYER_LEFT:
                validated = PlayerLeftSchema(**data)
                return PlayerLeft(player_id=validated.player_id)

            if message_type == MessageType.PLAYER_DISCONNECTED:
                validated = PlayerDisconnectedSchema(**data)
                return PlayerDisconnected(player_id=validated.player_id)

            raise DeserializationError(f"Unsupported WebSocket message type: {message_type}")

        except ValidationError as e:
            raise DeserializationError(
                f"Invalid WebSocket message format (type: {message_type}): {e.errors()}"
            )
