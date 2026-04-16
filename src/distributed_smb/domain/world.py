from dataclasses import dataclass, field

"""World state definitions."""


@dataclass(slots=True)
class CharacterState:
    """Minimal dynamic state for a controllable character."""

    player_id: str
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    width: int = 50
    height: int = 50
    on_ground: bool = False


@dataclass(slots=True)
class WorldState:
    """Authoritative world snapshot stored locally."""

    sequence_number: int = 0
    characters: dict[str, CharacterState] = field(default_factory=dict)

def add_player(self, player_id, character_state):
    self.characters[player_id] = character_state

def remove_player(self, player_id):
    del self.characters[player_id]

def get_player(self, player_id):
    return self.characters.get(player_id)

def get_all_players(self):
    return self.characters.values()

