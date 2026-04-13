"""Rendering abstractions for the game client."""

from dataclasses import dataclass

import pygame

from distributed_smb.domain.world import WorldState


@dataclass(slots=True)
class Renderer:
    """Minimal renderer placeholder for future Pygame integration."""

    width: int = 640
    height: int = 480
    background_color: tuple[int, int, int] = (135, 206, 235)
    player_color: tuple[int, int, int] = (220, 50, 50)
    platform_color: tuple[int, int, int] = (90, 60, 40)
    player_width: int = 32
    player_height: int = 48

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
                self.player_width,
                self.player_height,
            )
            pygame.draw.rect(screen, self.player_color, player_rect)

        pygame.display.flip()
