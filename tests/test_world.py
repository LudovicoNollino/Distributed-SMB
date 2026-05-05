from distributed_smb.domain.entity import CooperativeGate, DestructibleBlock, ExclusivePowerUp
from distributed_smb.domain.world import EnvironmentalState, WorldState, CharacterState


def test_environmental_state_contains_entities():
    env = EnvironmentalState()
    env.destructible_blocks.append(DestructibleBlock(x=10, y=10))
    env.power_ups["p1"] = ExclusivePowerUp(x=20, y=20, powerup_id="p1")
    env.cooperative_gates["g1"] = CooperativeGate(x=30, y=30, gate_id="g1")

    assert len(env.destructible_blocks) == 1
    assert "p1" in env.power_ups
    assert "g1" in env.cooperative_gates


def test_worldstate_preserves_environmental_state():
    world = WorldState()
    block = DestructibleBlock(x=10, y=10)
    world.environment.destructible_blocks.append(block)

    assert world.environment.destructible_blocks[0] is block