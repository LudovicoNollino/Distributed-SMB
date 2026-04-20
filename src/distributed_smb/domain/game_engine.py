"""Authoritative game simulation placeholder."""

from dataclasses import dataclass, field

from distributed_smb.domain.collisions import check_collision
from distributed_smb.domain.physics import JUMP_FORCE, MOVE_SPEED, apply_physics
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.config import WORLD_SCALE
from distributed_smb.shared.input import InputState


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)
    platforms: list = field(default_factory=list)

    def __post_init__(self) -> None:
        s = WORLD_SCALE
        self.platforms = [
            Platform(int(0 * s), int(300 * s), int(400 * s), int(50 * s)),
            Platform(int(450 * s), int(250 * s), int(200 * s), int(50 * s)),
            Platform(int(700 * s), int(350 * s), int(300 * s), int(50 * s)),
        ]

    def apply_inputs(self, inputs: dict[str, InputState]) -> None:
        for player_id, input_state in inputs.items():
            player = self.world_state.get_player(player_id)
            if not player:
                continue

            if input_state.left:
                player.vx = -MOVE_SPEED
            elif input_state.right:
                player.vx = MOVE_SPEED
            else:
                player.vx = 0

            if input_state.jump and player.on_ground:
                player.vy = JUMP_FORCE
                player.on_ground = False

    def tick(self, dt, inputs: dict[str, InputState]):
        self.apply_inputs(inputs)
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

    def spawn_player(self, player_id: str, x=100, y=100):
        player = CharacterState(player_id=player_id, x=x, y=y)
        self.world_state.add_player(player)


class Platform:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
