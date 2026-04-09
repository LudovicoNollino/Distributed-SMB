"""Leader election primitives."""

from dataclasses import dataclass


@dataclass(slots=True)
class ElectionResult:
    """Represents the outcome of a deterministic host election."""

    next_host_player_id: str | None = None
