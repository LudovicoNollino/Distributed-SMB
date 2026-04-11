"""Authoritative game simulation placeholder."""

from dataclasses import dataclass, field

from src.distributed_smb.domain.world import WorldState
from src.distributed_smb.domain.collisions import check_collision


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)

    def tick(self) -> None:
        """Advance the simulation by one logical step."""
        self.world_state.sequence_number += 1


class Platform:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        

def handle_collisions(self):
    self.player.on_ground = False

    for p in self.platforms:
        if check_collision(self.player, p):
            # semplice: atterra sopra
            if self.player.vy > 0:
                self.player.y = p.y - self.player.height
                self.player.vy = 0
                self.player.on_ground = True