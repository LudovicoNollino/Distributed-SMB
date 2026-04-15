from dataclasses import dataclass

"""Shared input contract used between presentation and domain."""


@dataclass(slots=True)
class InputState:
    """Represents the local player's gameplay intentions."""

    left: bool = False
    right: bool = False
    jump: bool = False
