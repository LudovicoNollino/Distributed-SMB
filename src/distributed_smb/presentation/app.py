"""Pygame application loop for the local presentation layer."""

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.world import WorldState
from distributed_smb.presentation.input_handler import ControlScheme, InputHandler
from distributed_smb.presentation.renderer import Renderer
from distributed_smb.shared.config import WINDOW_HEIGHT, WINDOW_WIDTH
from distributed_smb.shared.input import InputState


@dataclass
class GameApp:
    """Owns the local Pygame window and presentation loop."""

    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    fps: int = 60
    local_player_id: str = "player1"
    player2_id: str = "player2"
    engine: GameEngine = field(default_factory=GameEngine)
    input_handler: InputHandler = field(
        default_factory=lambda: InputHandler(control_scheme=ControlScheme.ARROWS)
    )
    player2_input_handler: InputHandler = field(
        default_factory=lambda: InputHandler(control_scheme=ControlScheme.WASD)
    )
    renderer: Renderer = field(default_factory=Renderer)
    frame_handler: Callable[[float, InputState], WorldState] | None = None

    def __post_init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Distributed SMB")
        self.clock = pygame.time.Clock()
        self._bootstrap_world()

    def _bootstrap_world(self) -> None:
        """Ensure the local player tracked by the engine exists in the world."""
        self._spawn_player_if_missing(self.local_player_id, x=100, y=100)
        self._spawn_player_if_missing(self.player2_id, x=240, y=100)

    def _spawn_player_if_missing(self, player_id: str, *, x: int, y: int) -> None:
        """Create one player in the shared world only when it is absent."""
        if self.engine.world_state.get_player(player_id) is None:
            self.engine.spawn_player(player_id, x=x, y=y)

    def _should_quit(self) -> bool:
        """Return True when the user asks to close the window."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
        return False

    def _clamp_player_to_window(self, player_id: str) -> None:
        """Keep one player within the visible screen bounds."""
        character = self.engine.world_state.get_player(player_id)
        if character is None:
            return

        min_x = 0
        max_x = self.width - character.width
        character.x = max(min_x, min(character.x, max_x))

    def _read_inputs(self) -> dict[str, InputState]:
        """Collect one shared input snapshot for every local player."""
        return {
            self.local_player_id: self.input_handler.read_input(),
            self.player2_id: self.player2_input_handler.read_input(),
        }

    def _build_platform_rects(self) -> list[pygame.Rect]:
        """Translate domain platforms into rectangles that the renderer can draw."""
        return [
            pygame.Rect(
                int(platform.x),
                int(platform.y),
                int(platform.width),
                int(platform.height),
            )
            for platform in self.engine.platforms
        ]

    def _update_window_caption(self) -> None:
        """Expose a little runtime context while the app loop is minimal."""
        character = self.get_local_player()
        player1 = self.engine.world_state.get_player("player1")
        player2 = self.engine.world_state.get_player("player2")
        player1_coords = (
            f"p1=({int(player1.x)},{int(player1.y)})" if player1 is not None else "p1=(missing)"
        )
        player2_coords = (
            f"p2=({int(player2.x)},{int(player2.y)})" if player2 is not None else "p2=(missing)"
        )
        pygame.display.set_caption(
            f"Distributed SMB [{self.local_player_id}] "
            f"| local=({int(character.x)},{int(character.y)}) "
            f"| {player1_coords} "
            f"| {player2_coords} "
            f"seq={self.engine.world_state.sequence_number}"
        )

    def run(self) -> None:
        """Start the graphical loop."""
        running = True

        while running:
            dt = self.clock.tick(self.fps) / 1000
            running = not self._should_quit()
            if self.frame_handler is None:
                inputs = self._read_inputs()
                self.engine.tick(dt, inputs)
                self._clamp_player_to_window(self.local_player_id)
                self._clamp_player_to_window(self.player2_id)
            else:
                local_input = self.input_handler.read_input()
                self.frame_handler(dt, local_input)
                self._clamp_player_to_window(self.local_player_id)
            self._update_window_caption()
            self.renderer.render(
                screen=self.screen,
                world_state=self.engine.world_state,
                platforms=self._build_platform_rects(),
            )

        pygame.quit()

    def get_local_player(self):
        return self.engine.world_state.get_player(self.local_player_id)
