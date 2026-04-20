"""Pygame application loop for the local presentation layer."""

from dataclasses import dataclass, field

import pygame

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.presentation.renderer import Renderer


@dataclass
class GameApp:
    """Owns the local Pygame window and presentation loop."""

    width: int = 640
    height: int = 480
    fps: int = 60
    local_player_id: str = "player1"
    engine: GameEngine = field(default_factory=GameEngine)
    input_handler: InputHandler = field(default_factory=InputHandler)
    renderer: Renderer = field(default_factory=Renderer)

    def __post_init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Distributed SMB")
        self.clock = pygame.time.Clock()
        self._bootstrap_world()

    def _bootstrap_world(self) -> None:
        """Ensure the local player tracked by the engine exists in the world."""
        if self.get_local_player() is None:
            self.engine.spawn_player(self.local_player_id)

    def _should_quit(self) -> bool:
        """Return True when the user asks to close the window."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
        return False

    def _clamp_local_player_to_window(self) -> None:
        """Keep the local player within the visible screen bounds."""
        character = self.get_local_player()
        min_x = 0
        max_x = self.width - self.renderer.player_width
        character.x = max(min_x, min(character.x, max_x))

    def _build_platform_rects(self) -> list[pygame.Rect]:
        """Translate domain platforms into rectangles that the renderer can draw."""
        return [
            pygame.Rect(platform.x, platform.y, platform.width, platform.height)
            for platform in self.engine.platforms
        ]

    def _update_window_caption(self) -> None:
        """Expose a little runtime context while the app loop is minimal."""
        character = self.get_local_player()
        pygame.display.set_caption(
            "Distributed SMB "
            f"| x={int(character.x)} y={int(character.y)} seq={self.engine.world_state.sequence_number}"
        )

    def run(self) -> None:
        """Start the graphical loop."""
        running = True

        while running:
            dt = self.clock.tick(self.fps) / 1000
            running = not self._should_quit()
            input_state = self.input_handler.read_input()
            inputs = {"player1": input_state}
            self.engine.tick(dt, inputs)
            self._clamp_local_player_to_window()
            self._update_window_caption()
            self.renderer.render(
                screen=self.screen,
                world_state=self.engine.world_state,
                platforms=self._build_platform_rects(),
            )

        pygame.quit()

    def get_local_player(self):
        return self.engine.world_state.get_player(self.local_player_id)