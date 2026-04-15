from dataclasses import dataclass, field

from distributed_smb.domain.collisions import check_collision
from distributed_smb.domain.physics import JUMP_FORCE, MOVE_SPEED, apply_physics
from distributed_smb.domain.world import CharacterState, WorldState

"""Authoritative game simulation placeholder."""


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)
    platforms: list = field(default_factory=list)
    local_player_id: str = "player1"

    def __post_init__(self):
        self.platforms = [
            Platform(0, 300, 400, 50),
            Platform(450, 250, 200, 50),
            Platform(700, 350, 300, 50),
        ]
        player = CharacterState(player_id="player1", x=100, y=100)
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

    def tick(self, dt):
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

    def get_local_player(self) -> CharacterState:
        return self.world_state.characters[self.local_player_id]


class Platform:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
