"""UDP transport placeholder."""

from dataclasses import dataclass


@dataclass(slots=True)
class UdpHandler:
    """Stores the endpoint used for real-time messages."""

    host: str
    port: int
