import pytest

from distributed_smb.domain.entity import (
    DestructibleBlock,
    ExclusivePowerUp,
)
from distributed_smb.domain.events import (
    BlockDestroyedEvent,
    PowerUpCollectedEvent,
)


def test_a_block_and_a_power_up_can_only_be_consumed_once():
    """The second attempt raises instead of emitting a second event: every
    node replays these events, so a duplicate would double every counter."""
    block = DestructibleBlock(x=100, y=100)
    event = block.destroy()
    assert block.destroyed is True
    assert isinstance(event, BlockDestroyedEvent)
    assert event.position == (100, 100)
    with pytest.raises(ValueError):
        block.destroy()

    power_up = ExclusivePowerUp(x=0, y=0, powerup_id="power1")
    event = power_up.collect("player1")
    assert power_up.collected is True
    assert power_up.owner == "player1"
    assert isinstance(event, PowerUpCollectedEvent)
    assert event.player_id == "player1"
    with pytest.raises(ValueError):
        power_up.collect("player2")
