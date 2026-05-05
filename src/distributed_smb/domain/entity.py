from dataclasses import dataclass, field
from typing import Iterable

from distributed_smb.domain.messages import (
    BlockDestroyedEvent,
    GateStateChangedEvent,
    PowerUpCollectedEvent,
    MessageValidationError,
    validate_player_id,
)


@dataclass(slots=True)
class DestructibleBlock:
    x: int
    y: int
    width: int = 32
    height: int = 32
    destroyed: bool = False

    def destroy(self) -> BlockDestroyedEvent:
        if self.destroyed:
            raise MessageValidationError(f"Block at {self.position} is already destroyed")
        self.destroyed = True
        return BlockDestroyedEvent(position=self.position)


@dataclass(slots=True)
class ExclusivePowerUp:
    x: int
    y: int
    width: int = 32
    height: int = 32
    powerup_id: str
    collected: bool = False
    owner: str | None = None

    def collect(self, player_id: str) -> PowerUpCollectedEvent:
        validate_player_id(player_id)

        if self.collected:
            raise MessageValidationError(
                f"Power-up {self.powerup_id} is already collected by {self.owner}"
            )

        self.collected = True
        self.owner = player_id
        return PowerUpCollectedEvent(powerup_id=self.powerup_id, player_id=player_id)


@dataclass(slots=True)
class CooperativeGate:
    x: int
    y: int
    width: int = 32
    height: int = 32
    gate_id: str
    state: str = "closed"
    contributions: set[str] = field(default_factory=set)

    def contribute(self, player_id: str) -> None:
        validate_player_id(player_id)
        self.contributions.add(player_id)

    def update_state(self, active_player_ids: Iterable[str]) -> GateStateChangedEvent | None:
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
        return GateStateChangedEvent(gate_id=self.gate_id, new_state=self.state)
