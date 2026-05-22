from copy import deepcopy

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.prediction_engine import PredictionEngine
from distributed_smb.shared.config import DIVERGENCE_THRESHOLD
from distributed_smb.shared.input import InputState


def test_prediction_engine_rolls_back_on_divergence_above_threshold():
    engine = GameEngine()
    engine.spawn_player("player1")
    prediction_engine = PredictionEngine(engine=engine, local_player_id="player1")

    predicted_state = prediction_engine.predict(1, InputState(right=True), 1 / 60)
    authoritative_snapshot = deepcopy(predicted_state)
    authoritative_snapshot.get_player("player1").x -= DIVERGENCE_THRESHOLD + 1
    authoritative_snapshot.sequence_number = 1

    rolled_back = prediction_engine.reconcile(authoritative_snapshot, 1 / 60)

    assert rolled_back is True
    assert prediction_engine.buffer.get_unacknowledged() == []
    authoritative = authoritative_snapshot.get_player("player1").x
    assert engine.world_state.get_player("player1").x == authoritative


def test_prediction_engine_does_not_rollback_for_small_divergence():
    engine = GameEngine()
    engine.spawn_player("player1")
    prediction_engine = PredictionEngine(engine=engine, local_player_id="player1")

    predicted_state = prediction_engine.predict(1, InputState(right=True), 1 / 60)
    authoritative_snapshot = deepcopy(predicted_state)
    authoritative_snapshot.get_player("player1").x += DIVERGENCE_THRESHOLD / 2
    authoritative_snapshot.sequence_number = 1

    rolled_back = prediction_engine.reconcile(authoritative_snapshot, 1 / 60)

    assert rolled_back is False
    assert prediction_engine.buffer.get_unacknowledged() == []
    assert engine.world_state.get_player("player1").x == predicted_state.get_player("player1").x


def test_prediction_engine_replays_unconfirmed_inputs_after_rollback():
    engine = GameEngine()
    engine.spawn_player("player1")
    prediction_engine = PredictionEngine(engine=engine, local_player_id="player1")

    prediction_engine.predict(1, InputState(right=True), 1 / 60)
    prediction_engine.predict(2, InputState(right=True), 1 / 60)

    authoritative_engine = GameEngine()
    authoritative_engine.spawn_player("player1")
    authoritative_snapshot = deepcopy(authoritative_engine.world_state)
    authoritative_snapshot.sequence_number = 1

    rolled_back = prediction_engine.reconcile(authoritative_snapshot, 1 / 60)

    assert rolled_back is True
    assert len(prediction_engine.buffer.get_unacknowledged()) == 1

    expected_engine = GameEngine()
    expected_engine.spawn_player("player1")
    expected_engine.world_state = deepcopy(authoritative_snapshot)
    expected_engine.tick(1 / 60, {"player1": InputState(right=True)})
    expected = expected_engine.world_state.get_player("player1").x
    assert engine.world_state.get_player("player1").x == expected
    assert engine.world_state.sequence_number == expected_engine.world_state.sequence_number
