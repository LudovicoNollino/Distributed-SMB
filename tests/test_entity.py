import pytest

from distributed_smb.domain.entity import (
    CooperativeGate,
    DestructibleBlock,
    ExclusivePowerUp,
)
from distributed_smb.domain.events import BlockDestroyed, GateStateChanged, PowerUpCollected


def test_destructible_block_destroy_emits_event():
    block = DestructibleBlock(x=100, y=100)

    event = block.destroy()

    assert block.destroyed is True
    assert isinstance(event, BlockDestroyed)
    assert event.position == (100, 100)

    with pytest.raises(ValueError):
        block.destroy()


def test_exclusive_powerup_collects_only_once():
    power_up = ExclusivePowerUp(x=0, y=0, powerup_id="power1")
    event = power_up.collect("player1")

    assert power_up.collected is True
    assert power_up.owner == "player1"
    assert isinstance(event, PowerUpCollected)
    assert event.player_id == "player1"

    with pytest.raises(ValueError):
        power_up.collect("player2")


def test_cooperative_gate_opens_when_all_active_players_contributed():
    gate = CooperativeGate(x=0, y=0, gate_id="gate1")

    gate.contribute("player1")
    gate.contribute("player2")

    event = gate.update_state(["player1", "player2"])

    assert isinstance(event, GateStateChanged)
    assert gate.state == "open"
    assert event.new_state == "open"


def test_cooperative_gate_stays_closed_if_missing_contribution():
    gate = CooperativeGate(x=0, y=0, gate_id="gate1")
    gate.contribute("player1")

    event = gate.update_state(["player1", "player2"])

    assert event is None
    assert gate.state == "closed"
