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
    required_players: set[str] = field(default_factory=set)

    def update_state(self, active_player_ids: Iterable[str]) -> GateStateChangedEvent | None:
        active_set = set(active_player_ids)
        should_be_open = self.required_players and self.required_players.issubset(active_set)
        new_state = "open" if should_be_open else "closed"

        if new_state == self.state:
            return None

        self.state = new_state
        return GateStateChangedEvent(gate_id=self.gate_id, new_state=self.state)
