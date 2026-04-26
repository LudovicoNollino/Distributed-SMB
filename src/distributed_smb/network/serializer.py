"""Message serialization helpers."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Union

from distributed_smb.domain.messages import (
    GameStart,
    InitialStateSync,
    MessageType,
    PlayerInputPacket,
    RosterUpdate,
    SessionCreate,
    SessionCreated,
    SessionJoin,
    SessionJoined,
    WorldStateSnapshot,
)
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
]


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

        if message_type == MessageType.PLAYER_INPUT:
            return PlayerInputPacket(
                player_id=data["player_id"],
                sequence_number=data["sequence_number"],
                input_state=InputState(**data["input_state"]),
            )

        if message_type == MessageType.WORLD_STATE:
            characters = {
                player_id: CharacterState(**character_data)
                for player_id, character_data in data["world_state"]["characters"].items()
            }
            world_state = WorldState(
                sequence_number=data["world_state"]["sequence_number"],
                characters=characters,
            )
            return WorldStateSnapshot(
                sequence_number=data["sequence_number"],
                world_state=world_state,
            )

        raise ValueError(f"Unsupported UDP message type: {message_type}")

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

        if message_type == MessageType.SESSION_CREATE:
            return SessionCreate(
                player_id=data["player_id"],
                ip=data["ip"],
                udp_port=data["udp_port"],
            )

        if message_type == MessageType.SESSION_CREATED:
            return SessionCreated(
                session_id=data["session_id"],
                join_index=data["join_index"],
            )

        if message_type == MessageType.SESSION_JOIN:
            return SessionJoin(
                session_id=data["session_id"],
                player_id=data["player_id"],
                ip=data["ip"],
                port=data["port"],
            )

        if message_type == MessageType.SESSION_JOINED:
            return SessionJoined(join_index=data["join_index"])

        if message_type == MessageType.ROSTER_UPDATE:
            roster = GlobalRoster()
            for entry in data["roster"]["players"]:
                roster.add_player(
                    RosterEntry(
                        player_id=entry["player_id"],
                        host=entry["host"],
                        udp_port=entry["udp_port"],
                        join_index=entry["join_index"],
                        status=ConnectionStatus(entry["status"]),
                        is_host=entry["is_host"],
                    )
                )
            return RosterUpdate(roster=roster)

        if message_type == MessageType.GAME_START:
            return GameStart(session_id=data["session_id"])

        if message_type == MessageType.INITIAL_STATE_SYNC:
            characters = {
                pid: CharacterState(**cs) for pid, cs in data["world_state"]["characters"].items()
            }
            world_state = WorldState(
                sequence_number=data["world_state"]["sequence_number"],
                characters=characters,
            )
            return InitialStateSync(world_state=world_state)

        raise ValueError(f"Unsupported WebSocket message type: {message_type}")
