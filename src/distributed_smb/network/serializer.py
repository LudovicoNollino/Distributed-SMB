"""Message serialization helpers."""

import json
from dataclasses import asdict, is_dataclass


class Serializer:
    """Serialize basic Python objects and dataclasses to JSON."""

    def encode(self, payload: object) -> str:
        """Encode the given payload to JSON."""
        if is_dataclass(payload):
            payload = asdict(payload)
        return json.dumps(payload)
