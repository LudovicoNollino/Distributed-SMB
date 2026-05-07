from dataclasses import dataclass, field
from typing import Iterable

from distributed_smb.domain.events import BlockDestroyed, GateStateChanged, PowerUpCollected


@dataclass(slots=True)
class DestructibleBlock:
    x: int
    y: int
    width: int = 32
    height: int = 32
    destroyed: bool = False

    def destroy(self) -> BlockDestroyed:
        if self.destroyed:
            raise ValueError(f"Block at {self.x}, {self.y} is already destroyed")
        self.destroyed = True
        return BlockDestroyed(position=(self.x, self.y))


@dataclass(slots=True)
class ExclusivePowerUp:
    x: int
    y: int
    powerup_id: str
    width: int = 32
    height: int = 32
    collected: bool = False
    owner: str | None = None

    def collect(self, player_id: str) -> PowerUpCollected:
        if self.collected:
            raise ValueError(f"Power-up {self.powerup_id} is already collected by {self.owner}")

        self.collected = True
        self.owner = player_id
        return PowerUpCollected(powerup_id=self.powerup_id, player_id=player_id)


@dataclass(slots=True)
class CooperativeGate:
    x: int
    y: int
    gate_id: str
    width: int = 32
    height: int = 32
    state: str = "closed"
    contributions: set[str] = field(default_factory=set)

    def contribute(self, player_id: str) -> None:
        self.contributions.add(player_id)

    def update_state(self, active_player_ids: Iterable[str]) -> GateStateChanged | None:
        active_set = set(active_player_ids)

        # Se non ci sono player attivi, il gate rimane chiuso
        should_be_open = bool(active_set) and active_set.issubset(self.contributions)

        if should_be_open:
            new_state = "open"
        else:
            new_state = "closed"

        if new_state == self.state:
            return None

        self.state = new_state
        return GateStateChanged(gate_id=self.gate_id, new_state=self.state)
