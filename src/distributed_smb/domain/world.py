"""World state definitions."""

from dataclasses import dataclass, field

from distributed_smb.shared.config import PLAYER_HEIGHT, PLAYER_WIDTH


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


@dataclass(slots=True)
class WorldState:
    """Authoritative world snapshot stored locally."""

    sequence_number: int = 0
    characters: dict[str, CharacterState] = field(default_factory=dict)

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

