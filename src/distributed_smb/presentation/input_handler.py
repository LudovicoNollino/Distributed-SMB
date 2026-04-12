"""Input capture abstractions for the local player."""

import logging
from dataclasses import dataclass, field

from distributed_smb.shared.input import InputState

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class InputHandler:
    """Collects and stores the latest local input snapshot."""

    pressed_actions: set[str] = field(default_factory=set)
    current_input: InputState = field(default_factory=InputState)

    def read_input(self) -> InputState:
        """Return the latest logical input snapshot."""
        LOGGER.info(
            "Input snapshot ready: left=%s, right=%s, jump=%s",
            self.current_input.left,
            self.current_input.right,
            self.current_input.jump,
        )
        return self.current_input
