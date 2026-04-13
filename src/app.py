"""Pygame application loop for the local presentation layer."""

from dataclasses import dataclass, field

import pygame

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.world import CharacterState
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.presentation.renderer import Renderer


@dataclass
class GameApp:
    """Owns the local Pygame window and presentation loop."""

    width: int = 640
    height: int = 480
    fps: int = 60
    local_player_id: str = "player-1"
    engine: GameEngine = field(default_factory=GameEngine)
    input_handler: InputHandler = field(default_factory=InputHandler)

    def __post_init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Distributed SMB")
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(width=self.width, height=self.height)
        self.platforms = [
            pygame.Rect(0, self.height - 40, self.width, 40),
            pygame.Rect(120, 330, 140, 20),
            pygame.Rect(320, 250, 160, 20),
        ]
        self._bootstrap_world()

    def _bootstrap_world(self) -> None:
        """Create a minimal local world until domain logic is wired in."""
        self.engine.world_state.characters[self.local_player_id] = CharacterState(
            player_id=self.local_player_id,
            x=80,
            y=120,
        )

    def _should_quit(self) -> bool:
        """Return True when the user asks to close the window."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
        return False

    def run(self) -> None:
        """Start the graphical loop."""
        running = True

        while running:
            running = not self._should_quit()

            input_state = self.input_handler.read_input()
            self.engine.tick()

            pygame.display.set_caption(
                "Distributed SMB "
                f"| left={input_state.left} right={input_state.right} jump={input_state.jump}"
            )

            self.renderer.render(
                screen=self.screen,
                world_state=self.engine.world_state,
                platforms=self.platforms,
            )

            self.clock.tick(self.fps)

        pygame.quit()


def main() -> None:
    """Run the local presentation app."""
    GameApp().run()


if __name__ == "__main__":
    main()
