"""Message serialization helpers."""

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from distributed_smb.domain.messages import MessageType, PlayerInputPacket, WorldStateSnapshot
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.input import InputState


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

    def encode_message(self, payload: PlayerInputPacket | WorldStateSnapshot) -> bytes:
        """Encode a milestone M2 packet to bytes ready for UDP transport."""
        return self.encode(payload).encode("utf-8")

    def decode_message(self, payload: str | bytes) -> PlayerInputPacket | WorldStateSnapshot:
        """Decode a milestone M2 packet into its typed dataclass."""
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

        raise ValueError(f"Unsupported message type: {message_type}")
