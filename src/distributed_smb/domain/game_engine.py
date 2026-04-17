"""Authoritative game simulation placeholder."""

from dataclasses import dataclass, field

from distributed_smb.domain.collisions import check_collision
from distributed_smb.domain.physics import JUMP_FORCE, MOVE_SPEED, apply_physics
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.config import WORLD_SCALE


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)
    platforms: list = field(default_factory=list)
    local_player_id: str = "player1"

    def __post_init__(self) -> None:
        s = WORLD_SCALE
        self.platforms = [
            Platform(int(0 * s), int(300 * s), int(400 * s), int(50 * s)),
            Platform(int(450 * s), int(250 * s), int(200 * s), int(50 * s)),
            Platform(int(700 * s), int(350 * s), int(300 * s), int(50 * s)),
        ]
        player = CharacterState(
            player_id=self.local_player_id,
            x=float(int(100 * s)),
            y=float(int(100 * s)),
        )
        self.world_state.characters[player.player_id] = player

    def apply_input(self, input_state) -> None:
        player = self.get_local_player()

        if input_state.left:
            player.vx = -MOVE_SPEED
        elif input_state.right:
            player.vx = MOVE_SPEED
        else:
            player.vx = 0

        if input_state.jump and player.on_ground:
            player.vy = JUMP_FORCE
            player.on_ground = False

    def tick(self, dt: float) -> None:
        """Advance the simulation by one logical step."""
        for player in self.world_state.characters.values():
            apply_physics(player, dt)
        self.handle_collisions()
        self.world_state.sequence_number += 1

    def handle_collisions(self) -> None:
        for player in self.world_state.characters.values():
            player.on_ground = False

            for platform in self.platforms:
                if check_collision(player, platform) and player.vy > 0:
                    player.y = platform.y - player.height
                    player.vy = 0
                    player.on_ground = True

    def get_local_player(self) -> CharacterState:
        return self.world_state.characters[self.local_player_id]


class Platform:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
