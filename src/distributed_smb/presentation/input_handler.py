"""Input capture abstractions for the local player."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class InputHandler:
    """Collects and stores the latest local input snapshot."""

    pressed_actions: set[str] = field(default_factory=set)
