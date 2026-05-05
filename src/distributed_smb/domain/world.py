"""World state definitions."""

from dataclasses import dataclass, field

from distributed_smb.shared.config import PLAYER_HEIGHT, PLAYER_WIDTH
from distributed_smb.domain.entity import CooperativeGate, DestructibleBlock, ExclusivePowerUp
@dataclass(slots=True)
class CharacterState:
    """Minimal dynamic state for a controllable character."""

    player_id: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    width: int = PLAYER_WIDTH
    height: int = PLAYER_HEIGHT
    on_ground: bool = False
    prev_x: float = 0.0
    prev_y: float = 0.0
    join_index: int = 0

@dataclass(slots=True)
class EnvironmentalState:
    destructible_blocks: list[DestructibleBlock] = field(default_factory=list)
    power_ups: dict[str, ExclusivePowerUp] = field(default_factory=dict)
    cooperative_gates: dict[str, CooperativeGate] = field(default_factory=dict)

@dataclass(slots=True)
class WorldState:
    """Authoritative world snapshot stored locally."""

    sequence_number: int = 0
    characters: dict[str, CharacterState] = field(default_factory=dict)
    environment: EnvironmentalState = field(default_factory=EnvironmentalState)

    def add_player(self, character: CharacterState):
        self.characters[character.player_id] = character

    def remove_player(self, player_id: str):
        if player_id in self.characters:
            del self.characters[player_id]

    def get_player(self, player_id: str) -> CharacterState | None:
        return self.characters[player_id] if player_id in self.characters else None

    def get_all_players(self):
        return list(self.characters.values())

    def get_all_players_dict(self):
        return self.characters
    
    def add_block(self, block: DestructibleBlock) -> None:
        self.environment.destructible_blocks.append(block)

    def get_block(self, position: tuple[int, int]) -> DestructibleBlock | None:
        for block in self.environment.destructible_blocks:
            if block.position == position:
                return block
        return None

    def add_power_up(self, power_up: ExclusivePowerUp) -> None:
        self.environment.power_ups[power_up.id] = power_up

    def get_power_up(self, powerup_id: str) -> ExclusivePowerUp | None:
        return self.environment.power_ups.get(powerup_id)

    def add_gate(self, gate: CooperativeGate) -> None:
        self.environment.cooperative_gates[gate.id] = gate

    def get_gate(self, gate_id: str) -> CooperativeGate | None:
        return self.environment.cooperative_gates.get(gate_id)

