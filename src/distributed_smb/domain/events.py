# domain/events.py
from dataclasses import dataclass


@dataclass(slots=True)
class BlockDestroyed:
    position: tuple[int, int]


@dataclass(slots=True)
class PowerUpCollected:
    powerup_id: str
    player_id: str


@dataclass(slots=True)
class GateStateChanged:
    gate_id: str
    new_state: str
