"""Authoritative game simulation placeholder."""

from dataclasses import dataclass, field

from distributed_smb.domain.collisions import check_collision, resolve_collision
from distributed_smb.domain.entity import CooperativeGate, DestructibleBlock, ExclusivePowerUp
from distributed_smb.domain.physics import JUMP_FORCE, MOVE_SPEED, apply_physics
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.config import WINDOW_HEIGHT, WINDOW_WIDTH
from distributed_smb.shared.input import InputState

BLOCK_SIZE = 36
POWERUP_SIZE = 34
GATE_WIDTH = 54
GATE_HEIGHT = 96


@dataclass(slots=True)
class GameEngine:
    """Owns the local world simulation and the default playable level."""

    world_state: WorldState = field(default_factory=WorldState)
    platforms: list = field(default_factory=list)
    events: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self._build_default_level()

    def _build_default_level(self) -> None:
        """Create a compact level where all objects are visible and reachable."""
        floor_y = WINDOW_HEIGHT - 90
        self.platforms = [
            Platform(0, floor_y, WINDOW_WIDTH, 60),
            Platform(165, floor_y - 100, 230, 30),
            Platform(430, floor_y - 190, 230, 30),
            Platform(690, floor_y - 100, 205, 30),
            Platform(720, floor_y - 225, 165, 30),
        ]
        self._seed_default_environment()

    def _seed_default_environment(self) -> None:
        env = self.world_state.environment
        env.destructible_blocks.clear()
        env.power_ups.clear()
        env.cooperative_gates.clear()

        self.world_state.add_block(
            DestructibleBlock(x=230, y=420, width=BLOCK_SIZE, height=BLOCK_SIZE)
        )
        self.world_state.add_block(
            DestructibleBlock(x=270, y=420, width=BLOCK_SIZE, height=BLOCK_SIZE)
        )
        self.world_state.add_block(
            DestructibleBlock(x=510, y=330, width=BLOCK_SIZE, height=BLOCK_SIZE)
        )
        self.world_state.add_block(
            DestructibleBlock(x=550, y=330, width=BLOCK_SIZE, height=BLOCK_SIZE)
        )
        self.world_state.add_block(
            DestructibleBlock(x=760, y=295, width=BLOCK_SIZE, height=BLOCK_SIZE)
        )

        self.world_state.add_power_up(
            ExclusivePowerUp(
                x=335,
                y=486,
                width=POWERUP_SIZE,
                height=POWERUP_SIZE,
                powerup_id="pu-test",
            )
        )
        self.world_state.add_power_up(
            ExclusivePowerUp(
                x=610,
                y=396,
                width=POWERUP_SIZE,
                height=POWERUP_SIZE,
                powerup_id="pu-mid",
            )
        )
        self.world_state.add_power_up(
            ExclusivePowerUp(
                x=816,
                y=361,
                width=POWERUP_SIZE,
                height=POWERUP_SIZE,
                powerup_id="pu-high",
            )
        )

        self.world_state.add_gate(
            CooperativeGate(
                x=820,
                y=WINDOW_HEIGHT - 90 - GATE_HEIGHT,
                width=GATE_WIDTH,
                height=GATE_HEIGHT,
                gate_id="gate-test",
            )
        )

    def apply_inputs(self, inputs: dict[str, InputState]) -> None:
        for player_id, input_state in inputs.items():
            player = self.world_state.get_player(player_id)
            if not player:
                continue

            if input_state.left:
                player.vx = -MOVE_SPEED
            elif input_state.right:
                player.vx = MOVE_SPEED
            else:
                player.vx = 0

            if input_state.jump and player.on_ground:
                player.vy = JUMP_FORCE
                player.on_ground = False

    def tick(self, dt, inputs: dict[str, InputState]):
        for player in self.world_state.characters.values():
            player.prev_x = player.x
            player.prev_y = player.y

        self.apply_inputs(inputs)
        for player in self.world_state.characters.values():
            apply_physics(player, dt)

        self.handle_collisions()
        self.handle_block_collisions()
        self.handle_powerup_collisions()
        self.handle_gate_collisions()
        self.world_state.sequence_number += 1

    def handle_collisions(self) -> None:
        for player in self.world_state.characters.values():
            player.on_ground = False

            for platform in self.platforms:
                if check_collision(player, platform):
                    resolve_collision(player, platform)

    def spawn_player(self, player_id: str, x=100, y=100, join_index: int = 0):
        player = CharacterState(player_id=player_id, x=x, y=y, join_index=join_index)
        self.world_state.add_player(player)

    def handle_environment_collisions(self) -> None:
        self.handle_block_collisions()
        self.handle_powerup_collisions()
        self.handle_gate_collisions()

    def handle_block_collisions(self) -> None:
        for player in self.world_state.characters.values():
            for block in self.world_state.environment.destructible_blocks:
                if not block.destroyed and check_collision(player, block):
                    if self._is_head_bump(player, block):
                        event = block.destroy()
                        self.events.append(event)
                    else:
                        resolve_collision(player, block)

    def handle_powerup_collisions(self) -> None:
        for power_up in self.world_state.environment.power_ups.values():
            if power_up.collected:
                continue

            colliding_players = [
                player
                for player in self.world_state.characters.values()
                if check_collision(player, power_up)
            ]

            if not colliding_players:
                continue

            winner = min(colliding_players, key=lambda p: p.join_index)
            event = power_up.collect(winner.player_id)
            self.events.append(event)

    def handle_gate_collisions(self) -> None:
        active_players = self.world_state.get_all_players_dict().keys()
        for gate in self.world_state.environment.cooperative_gates.values():
            colliding_players = [
                player
                for player in self.world_state.characters.values()
                if check_collision(player, gate)
            ]
            for player in colliding_players:
                gate.contribute(player.player_id)
            event = gate.update_state(active_players)
            if event is not None:
                self.events.append(event)
            if gate.state == "closed":
                for player in colliding_players:
                    resolve_collision(player, gate)

    def _is_head_bump(self, player: CharacterState, block: DestructibleBlock) -> bool:
        return (
            player.vy < 0
            and player.prev_y >= block.y + block.height
            and player.y < block.y + block.height
        )


class Platform:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
