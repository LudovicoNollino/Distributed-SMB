"""Shared input contract used between presentation and domain."""
from dataclasses import dataclass

@dataclass(slots=True)
class InputState:
    """Represents the local player's gameplay intentions."""

    left: bool = False
    right: bool = False
    jump: bool = False

