"""Rendering abstractions for the game client."""

from dataclasses import dataclass

import pygame

from distributed_smb.domain.world import WorldState
from distributed_smb.shared.config import WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass(slots=True)
class Renderer:
    """Minimal renderer placeholder for future Pygame integration."""

    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    background_color: tuple[int, int, int] = (135, 206, 235)
    platform_color: tuple[int, int, int] = (90, 60, 40)
    player_palette: dict[str, tuple[int, int, int]] = None

    def __post_init__(self) -> None:
        if self.player_palette is None:
            self.player_palette = {
                "player1": (220, 50, 50),
                "player2": (50, 90, 220),
            }

    def render(
        self,
        screen: pygame.Surface,
        world_state: WorldState,
        platforms: list[pygame.Rect],
    ) -> None:
        """Render one frame of the game world."""
        screen.fill(self.background_color)

        for platform in platforms:
            pygame.draw.rect(screen, self.platform_color, platform)

        for character in world_state.characters.values():
            player_rect = pygame.Rect(
                int(character.x),
                int(character.y),
                int(character.width),
                int(character.height),
            )
            color = self.player_palette.get(character.player_id, (80, 80, 80))
            pygame.draw.rect(screen, color, player_rect)

        pygame.display.flip()
