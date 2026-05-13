"""Rendering abstractions for the game client."""

from dataclasses import dataclass, field

import pygame

from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.config import WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass(slots=True)
class Renderer:
    """Render the scene and player sprites for the local client."""

    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    background_color: tuple[int, int, int] = (135, 206, 235)
    platform_color: tuple[int, int, int] = (90, 60, 40)
    player_palette: dict[str, tuple[int, int, int]] = None
    _sprite_cache: dict[
        tuple[tuple[int, int, int], str, int, int, int, int], pygame.Surface
    ] = field(init=False, default_factory=dict)
    _facing_by_player: dict[str, int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        if self.player_palette is None:
            self.player_palette = {
                "player1": (220, 50, 50),
                "player2": (50, 90, 220),
            }

    def _resolve_facing(self, character: CharacterState) -> int:
        """Keep the latest horizontal facing direction for each player."""
        if character.vx > 0:
            facing = 1
        elif character.vx < 0:
            facing = -1
        else:
            facing = self._facing_by_player.get(character.player_id, 1)
        self._facing_by_player[character.player_id] = facing
        return facing

    def _animation_state(self, character: CharacterState) -> str:
        """Classify the current sprite state from physics data."""
        if not character.on_ground:
            return "jump"
        if abs(character.vx) > 1:
            return "walk"
        return "idle"

    def _animation_frame(self, state: str) -> int:
        """Return the frame index for the current animation state."""
        if state == "walk":
            return (pygame.time.get_ticks() // 140) % 2
        return 0

    def _shade(self, color: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
        return tuple(max(0, min(255, channel + delta)) for channel in color)

    def _draw_sprite_frame(
        self,
        surface: pygame.Surface,
        state: str,
        frame: int,
        body_color: tuple[int, int, int],
    ) -> None:
        """Draw a simple pixel-art plumber-like sprite into the target surface."""
        width, height = surface.get_size()
        skin = (247, 214, 177)
        hat = self._shade(body_color, -25)
        shirt = self._shade(body_color, 20)
        overalls = self._shade(body_color, -50)
        boots = (102, 68, 32)
        eye = (20, 20, 20)

        def rect(rx: float, ry: float, rw: float, rh: float, color: tuple[int, int, int]) -> None:
            pygame.draw.rect(
                surface,
                color,
                pygame.Rect(
                    round(rx * width),
                    round(ry * height),
                    max(1, round(rw * width)),
                    max(1, round(rh * height)),
                ),
            )

        leg_offset = 0.04 if state == "walk" and frame == 1 else -0.04 if state == "walk" else 0.0
        arm_offset = -0.04 if state == "walk" and frame == 1 else 0.04 if state == "walk" else 0.0
        jump_raise = -0.03 if state == "jump" else 0.0

        rect(0.28, 0.07 + jump_raise, 0.44, 0.12, hat)
        rect(0.23, 0.17 + jump_raise, 0.54, 0.06, hat)
        rect(0.32, 0.23 + jump_raise, 0.36, 0.18, skin)
        rect(0.6, 0.29 + jump_raise, 0.05, 0.05, eye)
        rect(0.35, 0.42 + jump_raise, 0.3, 0.12, shirt)
        rect(0.26, 0.42 + arm_offset + jump_raise, 0.08, 0.22, shirt)
        rect(0.66, 0.42 - arm_offset + jump_raise, 0.08, 0.22, shirt)
        rect(0.32, 0.54 + jump_raise, 0.36, 0.16, overalls)
        rect(0.39, 0.56 + jump_raise, 0.06, 0.14, shirt)
        rect(0.55, 0.56 + jump_raise, 0.06, 0.14, shirt)
        rect(0.34, 0.7 + leg_offset + jump_raise, 0.12, 0.16, boots)
        rect(0.54, 0.7 - leg_offset + jump_raise, 0.12, 0.16, boots)

    def _build_sprite(
        self,
        body_color: tuple[int, int, int],
        state: str,
        frame: int,
        width: int,
        height: int,
        facing: int,
    ) -> pygame.Surface:
        sprite = pygame.Surface((width, height), pygame.SRCALPHA)
        shadow = pygame.Rect(width // 5, height - max(4, height // 10), width * 3 // 5, max(4, height // 12))
        pygame.draw.ellipse(sprite, (0, 0, 0, 60), shadow)
        self._draw_sprite_frame(sprite, state, frame, body_color)
        if facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        return sprite

    def _get_player_sprite(self, character: CharacterState) -> pygame.Surface:
        """Return a cached sprite frame for the given character state."""
        color = self.player_palette.get(character.player_id, (80, 80, 80))
        state = self._animation_state(character)
        frame = self._animation_frame(state)
        facing = self._resolve_facing(character)
        cache_key = (color, state, frame, character.width, character.height, facing)
        sprite = self._sprite_cache.get(cache_key)
        if sprite is None:
            sprite = self._build_sprite(
                body_color=color,
                state=state,
                frame=frame,
                width=int(character.width),
                height=int(character.height),
                facing=facing,
            )
            self._sprite_cache[cache_key] = sprite
        return sprite

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

        for character in sorted(world_state.characters.values(), key=lambda c: (c.y, c.player_id)):
            player_rect = pygame.Rect(
                int(character.x),
                int(character.y),
                int(character.width),
                int(character.height),
            )
            screen.blit(self._get_player_sprite(character), player_rect.topleft)

        pygame.display.flip()
