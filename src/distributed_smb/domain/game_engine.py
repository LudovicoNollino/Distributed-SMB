from dataclasses import dataclass, field

from distributed_smb.domain.collisions import check_collision
from distributed_smb.domain.physics import JUMP_FORCE, MOVE_SPEED, apply_physics
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.input import InputState

"""Authoritative game simulation placeholder."""


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)
    platforms: list = field(default_factory=list)

    def __post_init__(self):
        self.platforms = [
            Platform(0, 300, 400, 50),
            Platform(450, 250, 200, 50),
            Platform(700, 350, 300, 50),
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
        """Advance the simulation by one logical step."""
        self.world_state.sequence_number += 1

    def handle_collisions(self):
        for player in self.world_state.characters.values():
            player.on_ground = False

            for p in self.platforms:
                if check_collision(player, p):
                    if player.vy > 0:
                        player.y = p.y - player.height
                        player.vy = 0
                        player.on_ground = True

    def spawn_player(self, player_id: str, x=100, y=100):
        player = CharacterState(player_id=player_id, x=x, y=y)
        self.world_state.add_player(player)


class Platform:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
