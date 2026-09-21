from copy import deepcopy

import pytest

from distributed_smb.application.reconciliation import PredictionEngine
from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.world import WorldState
from distributed_smb.shared.config import TICK_INTERVAL
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


def _make_snapshot(world_state: WorldState) -> WorldStateSnapshot:
    return WorldStateSnapshot(
        sequence_number=world_state.sequence_number,
        world_state=world_state,
    )


def test_predict_records_the_input_without_advancing_the_engine():
    """The caller ticks the engine: predict() only remembers the input so the
    reconciliation can replay it later."""
    engine = GameEngine()
    engine.spawn_player("player1")
    pe = PredictionEngine(engine=engine, local_player_id="player1")
    seq_before = engine.world_state.sequence_number

    assert pe.buffer.get_unacknowledged() == []
    pe.predict(InputState(right=True))

    assert engine.world_state.sequence_number == seq_before
    assert len(pe.buffer.get_unacknowledged()) == 1


def test_reconcile_takes_characters_and_enemies_but_keeps_local_environment():
    """Enemies have no WS event, so they must come from the snapshot; blocks,
    power-ups and gates have one, so the local prediction wins."""
    engine = GameEngine()
    engine.spawn_player("player1")
    pe = PredictionEngine(engine=engine, local_player_id="player1")

    local_enemy = next(iter(engine.world_state.environment.enemies.values()))
    local_enemy.x = 111.0
    engine.world_state.environment.destructible_blocks[0].destroyed = True

    authoritative = deepcopy(engine.world_state)
    authoritative.get_player("player1").x = 999.0
    next(iter(authoritative.environment.enemies.values())).x = 500.0
    authoritative.environment.destructible_blocks[0].destroyed = False

    pe.reconcile(_make_snapshot(authoritative))

    assert engine.world_state.get_player("player1").x == 999.0
    assert next(iter(engine.world_state.environment.enemies.values())).x == 500.0
    assert engine.world_state.environment.destructible_blocks[0].destroyed is True


def test_reconcile_replays_the_unacknowledged_inputs_and_drops_the_rest():
    """The client re-applies what the host has not seen yet, and forgets what
    it has: a buffer that never shrinks would replay the whole session."""
    engine = GameEngine()
    engine.spawn_player("player1")
    pe = PredictionEngine(engine=engine, local_player_id="player1")

    for _ in range(2):
        pe.predict(InputState(right=True))
        engine.tick(TICK_INTERVAL, {"player1": InputState(right=True)})
    assert len(pe.buffer.get_unacknowledged()) == 2

    # The host has only applied the first of the two inputs.
    host_engine = GameEngine()
    host_engine.spawn_player("player1")
    host_engine.tick(TICK_INTERVAL, {"player1": InputState(right=True)})

    pe.reconcile(_make_snapshot(deepcopy(host_engine.world_state)))

    expected = GameEngine()
    expected.spawn_player("player1")
    expected.world_state = deepcopy(host_engine.world_state)
    expected.tick(TICK_INTERVAL, {"player1": InputState(right=True)})

    assert engine.world_state.get_player("player1").x == pytest.approx(
        expected.world_state.get_player("player1").x
    )
    assert len(pe.buffer.get_unacknowledged()) == 1


def test_reconcile_drops_input_history_orphaned_by_a_host_migration():
    """A new host resumes from an older sequence: inputs buffered against the
    old timeline can never be acknowledged and must be dropped."""
    engine = GameEngine()
    engine.spawn_player("player1")
    pe = PredictionEngine(engine=engine, local_player_id="player1", history_capacity=60)

    # Client ran ahead locally while the old host was gone.
    engine.world_state.sequence_number = 2384
    for _ in range(60):
        pe.predict(InputState(right=True), TICK_INTERVAL)
        engine.tick(TICK_INTERVAL, {"player1": InputState(right=True)})
    assert pe.pending_count() == 60

    authoritative = deepcopy(engine.world_state)
    authoritative.sequence_number = 1450
    pe.reconcile(_make_snapshot(authoritative))

    assert pe.pending_count() == 0
    assert engine.world_state.sequence_number == 1450
