"""Input capture abstractions for the local player."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import pygame

from distributed_smb.shared.input import InputState

LOGGER = logging.getLogger(__name__)


def _pygame_key_provider() -> Any:
    return pygame.key.get_pressed()


class ControlScheme(StrEnum):
    """Supported keyboard layouts for the local player."""

    ARROWS = "arrows"
    WASD = "wasd"


@dataclass(slots=True)
class InputHandler:
    """Collects and stores the latest local input snapshot."""

    pressed_actions: set[str] = field(default_factory=set)
    current_input: InputState = field(default_factory=InputState)
    key_provider: Callable[[], Any] = field(default=_pygame_key_provider)
    control_scheme: ControlScheme = ControlScheme.ARROWS

    def read_input(self) -> InputState:
        """Return the latest logical input snapshot."""
        keys = self.key_provider()

        if self.control_scheme is ControlScheme.WASD:
            left = bool(keys[pygame.K_a])
            right = bool(keys[pygame.K_d])
            jump = bool(keys[pygame.K_w])
        else:
            left = bool(keys[pygame.K_LEFT])
            right = bool(keys[pygame.K_RIGHT])
            jump = bool(keys[pygame.K_UP])

        self.current_input = InputState(
            left=left,
            right=right,
            jump=jump,
        )

        # LOGGER.info(
        #     "Input snapshot ready: scheme=%s left=%s right=%s jump=%s",
        #     self.control_scheme,
        #     self.current_input.left,
        #     self.current_input.right,
        #     self.current_input.jump,
        # )
        return self.current_input
