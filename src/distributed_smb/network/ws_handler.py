"""WebSocket transport placeholder."""

from dataclasses import dataclass


@dataclass(slots=True)
class WsHandler:
    """Stores the endpoint used for reliable control messages."""

    host: str
    port: int
