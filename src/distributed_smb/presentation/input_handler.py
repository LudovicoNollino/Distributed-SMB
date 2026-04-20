"""Input capture abstractions for the local player."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pygame

from distributed_smb.shared.input import InputState

LOGGER = logging.getLogger(__name__)


def _pygame_key_provider() -> Any:
    return pygame.key.get_pressed()


@dataclass(slots=True)
class InputHandler:
    """Collects and stores the latest local input snapshot."""

    pressed_actions: set[str] = field(default_factory=set)
    current_input: InputState = field(default_factory=InputState)
    key_provider: Callable[[], Any] = field(default=_pygame_key_provider)

    def read_input(self) -> InputState:
        """Return the latest logical input snapshot."""
        keys = self.key_provider()

        self.current_input = InputState(
            left=bool(keys[pygame.K_LEFT] or keys[pygame.K_a]),
            right=bool(keys[pygame.K_RIGHT] or keys[pygame.K_d]),
            jump=bool(keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]),
        )

        LOGGER.info(
            "Input snapshot ready: left=%s, right=%s, jump=%s",
            self.current_input.left,
            self.current_input.right,
            self.current_input.jump,
        )
        return self.current_input
