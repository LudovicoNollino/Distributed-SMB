import json
from dataclasses import asdict

def serialize_message(message) -> str:
    return json.dumps(asdict(message))


def deserialize_message(data: str, cls):
    return cls(**json.loads(data))