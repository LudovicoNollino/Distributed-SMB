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
    _environment_sprite_cache: dict[tuple[str, str, int, int], pygame.Surface] = field(
        init=False, default_factory=dict
    )
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

    def _draw_block_surface(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        body = (177, 100, 46)
        mortar = (118, 62, 28)
        highlight = (224, 160, 98)
        pygame.draw.rect(surface, body, surface.get_rect(), border_radius=max(2, width // 10))
        pygame.draw.rect(surface, mortar, surface.get_rect(), width=max(2, width // 9))
        pygame.draw.line(surface, mortar, (width // 2, 3), (width // 2, height - 3), max(2, width // 12))
        pygame.draw.line(surface, mortar, (3, height // 2), (width - 3, height // 2), max(2, height // 12))
        pygame.draw.line(surface, highlight, (5, 5), (width - 5, 5), max(1, height // 14))

    def _draw_powerup_surface(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        glow_color = (255, 227, 107, 90)
        star_color = (255, 217, 52)
        shine = (255, 247, 205)
        center = (width // 2, height // 2)
        radius = max(6, min(width, height) // 2 - 3)
        pygame.draw.circle(surface, glow_color, center, radius)
        points = [
            (width * 0.50, height * 0.12),
            (width * 0.60, height * 0.38),
            (width * 0.88, height * 0.38),
            (width * 0.66, height * 0.56),
            (width * 0.76, height * 0.86),
            (width * 0.50, height * 0.68),
            (width * 0.24, height * 0.86),
            (width * 0.34, height * 0.56),
            (width * 0.12, height * 0.38),
            (width * 0.40, height * 0.38),
        ]
        pygame.draw.polygon(surface, star_color, [(round(x), round(y)) for x, y in points])
        pygame.draw.circle(surface, shine, (round(width * 0.43), round(height * 0.32)), max(2, width // 10))

    def _draw_gate_surface(self, surface: pygame.Surface, state: str) -> None:
        width, height = surface.get_size()
        frame = (92, 65, 40)
        closed_fill = (79, 127, 173)
        open_fill = (116, 195, 122)
        accent = (212, 233, 248) if state == "closed" else (215, 255, 220)
        fill = open_fill if state == "open" else closed_fill
        panel_width = max(4, width // 5)
        pygame.draw.rect(surface, frame, surface.get_rect(), border_radius=max(2, width // 10))
        inner = surface.get_rect().inflate(-max(4, width // 5), -max(4, height // 8))
        pygame.draw.rect(surface, fill, inner, border_radius=max(2, width // 12))
        pygame.draw.rect(surface, accent, inner, width=max(2, width // 12), border_radius=max(2, width // 12))
        if state == "open":
            opening = pygame.Rect(inner.centerx - panel_width // 2, inner.y, panel_width, inner.height)
            pygame.draw.rect(surface, (30, 30, 30, 0), opening)
            pygame.draw.rect(surface, (35, 45, 58), opening.inflate(-2, 0))
        else:
            pygame.draw.circle(
                surface,
                (255, 236, 135),
                (inner.centerx, inner.centery),
                max(3, min(width, height) // 9),
            )

    def _get_environment_sprite(
        self,
        sprite_kind: str,
        state: str,
        width: int,
        height: int,
    ) -> pygame.Surface:
        cache_key = (sprite_kind, state, width, height)
        sprite = self._environment_sprite_cache.get(cache_key)
        if sprite is not None:
            return sprite

        sprite = pygame.Surface((width, height), pygame.SRCALPHA)
        if sprite_kind == "block":
            self._draw_block_surface(sprite)
        elif sprite_kind == "powerup":
            self._draw_powerup_surface(sprite)
        elif sprite_kind == "gate":
            self._draw_gate_surface(sprite, state)
        self._environment_sprite_cache[cache_key] = sprite
        return sprite

    def _render_environment(self, screen: pygame.Surface, world_state: WorldState) -> None:
        for block in world_state.environment.destructible_blocks:
            if block.destroyed:
                continue
            screen.blit(
                self._get_environment_sprite("block", "intact", block.width, block.height),
                (int(block.x), int(block.y)),
            )

        for power_up in world_state.environment.power_ups.values():
            if power_up.collected:
                continue
            screen.blit(
                self._get_environment_sprite("powerup", "available", power_up.width, power_up.height),
                (int(power_up.x), int(power_up.y)),
            )

        for gate in world_state.environment.cooperative_gates.values():
            screen.blit(
                self._get_environment_sprite("gate", gate.state, gate.width, gate.height),
                (int(gate.x), int(gate.y)),
            )

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

        self._render_environment(screen, world_state)

        for character in sorted(world_state.characters.values(), key=lambda c: (c.y, c.player_id)):
            player_rect = pygame.Rect(
                int(character.x),
                int(character.y),
                int(character.width),
                int(character.height),
            )
            screen.blit(self._get_player_sprite(character), player_rect.topleft)

        pygame.display.flip()
