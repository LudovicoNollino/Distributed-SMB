"""Input capture abstractions for the local player."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pygame

from distributed_smb.shared.input import InputState


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
            left=bool(keys[pygame.K_LEFT]) or bool(keys[pygame.K_a]),
            right=bool(keys[pygame.K_RIGHT]) or bool(keys[pygame.K_d]),
            jump=bool(keys[pygame.K_UP]) or bool(keys[pygame.K_w]),
            down=bool(keys[pygame.K_DOWN]) or bool(keys[pygame.K_s]),
        )
        return self.current_input
