import json
from dataclasses import asdict, is_dataclass
from datetime import datetime


class DataclassJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for dataclasses and datetime objects."""

    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            # Handle dict with non-string keys by converting to list of tuples
            return {str(k): v for k, v in obj.items()}
        return super().default(obj)


def serialize_message(message) -> str:
    """Serialize a dataclass message to JSON string with support for nested dataclasses."""
    return json.dumps(asdict(message), cls=DataclassJSONEncoder)


def deserialize_message(data: str, cls):
    """Deserialize a JSON string to a dataclass instance."""
    return cls(**json.loads(data))
