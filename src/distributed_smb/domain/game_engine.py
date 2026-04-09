"""Authoritative game simulation placeholder."""

from dataclasses import dataclass, field

from distributed_smb.domain.world import WorldState


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation."""

    world_state: WorldState = field(default_factory=WorldState)

    def tick(self) -> None:
        """Advance the simulation by one logical step."""
        self.world_state.sequence_number += 1
