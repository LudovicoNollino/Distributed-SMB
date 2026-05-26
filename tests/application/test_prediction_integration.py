"""Integration tests for M5 prediction and reconciliation wiring."""

from distributed_smb.application.node_controller import NodeController
from distributed_smb.application.reconciliation import (
    NoopPredictionEngine,
    PredictionEngine,
    PredictionEngineProtocol,
)
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.config import (
    ARTIFICIAL_LATENCY_MS,
    DIVERGENCE_THRESHOLD,
    INPUT_HISTORY_SIZE,
    MAX_ROLLBACK_FRAMES,
    TICK_INTERVAL,
)
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeUdpHandler:
    """Minimal UDP stub: discards sends, returns an optional packet then None."""

    def __init__(self, packet: bytes | None = None):
        self._packet = packet

    def open_socket(self) -> None:
        pass

    def send_packet_nowait(self, payload, host, port) -> None:
        pass

    def receive_packet_nowait(self):
        if self._packet is None:
            return None
        packet, self._packet = self._packet, None
        return packet, ("127.0.0.1", 50010)


class _SpyPredictionEngine:
    """Records every call to predict() and reconcile() for inspection."""

    def __init__(self):
        self.predict_calls: list[InputState] = []
        self.reconcile_calls: list[WorldStateSnapshot] = []

    def predict(self, input_state: InputState) -> None:
        self.predict_calls.append(input_state)

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        self.reconcile_calls.append(authoritative_snapshot)

    def should_rollback(self, predicted, authoritative) -> bool:
        return False


def _make_snapshot_payload(nc: NodeController, seq: int = 1) -> bytes:
    return Serializer().encode_message(
        WorldStateSnapshot(sequence_number=seq, world_state=nc.engine.world_state)
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_noop_satisfies_prediction_engine_protocol():
    """NoopPredictionEngine must pass runtime isinstance check against the Protocol."""
    assert isinstance(NoopPredictionEngine(), PredictionEngineProtocol)


def test_spy_satisfies_prediction_engine_protocol():
    """_SpyPredictionEngine must also satisfy the Protocol (used throughout tests)."""
    assert isinstance(_SpyPredictionEngine(), PredictionEngineProtocol)


# ---------------------------------------------------------------------------
# NodeController wiring
# ---------------------------------------------------------------------------


def test_node_controller_wires_engine_to_noop_on_init():
    """__post_init__ must set _engine on NoopPredictionEngine so reconcile() works."""
    nc = NodeController()
    assert isinstance(nc.prediction_engine, NoopPredictionEngine)
    assert nc.prediction_engine._engine is nc.engine


def test_custom_prediction_engine_is_not_overridden():
    """When a non-noop engine is passed, __post_init__ must not touch it."""
    spy = _SpyPredictionEngine()
    nc = NodeController(prediction_engine=spy)
    assert nc.prediction_engine is spy


def test_client_bootstrap_wires_real_prediction_engine():
    """bootstrap(CLIENT) must replace NoopPredictionEngine with the real PredictionEngine."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    assert isinstance(nc.prediction_engine, PredictionEngine)
    assert nc.prediction_engine.engine is nc.engine
    assert nc.prediction_engine.local_player_id == nc.local_player_id


def test_host_bootstrap_keeps_noop_prediction_engine():
    """bootstrap(HOST) must keep NoopPredictionEngine — host never predicts."""
    nc = NodeController().bootstrap(role=PlayerRole.HOST)
    assert isinstance(nc.prediction_engine, NoopPredictionEngine)


# ---------------------------------------------------------------------------
# Calling contract — predict()
# ---------------------------------------------------------------------------


def test_predict_is_called_once_per_client_frame():
    """_process_client_frame must call prediction_engine.predict() exactly once."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler()

    input_state = InputState(right=True)
    nc.process_frame(TICK_INTERVAL, input_state)

    assert len(spy.predict_calls) == 1
    assert spy.predict_calls[0] == input_state


def test_predict_receives_the_exact_input_passed_to_process_frame():
    """predict() must receive the same InputState that was given to process_frame."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler()

    inp = InputState(left=True, jump=True)
    nc.process_frame(TICK_INTERVAL, inp)

    assert spy.predict_calls[0].left is True
    assert spy.predict_calls[0].jump is True


def test_predict_not_called_on_host_frame():
    """Host frames must never call predict() — prediction is client-side only."""
    nc = NodeController().bootstrap(role=PlayerRole.HOST)
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler()

    nc.process_frame(TICK_INTERVAL, InputState())

    assert spy.predict_calls == []


# ---------------------------------------------------------------------------
# Calling contract — reconcile()
# ---------------------------------------------------------------------------


def test_reconcile_is_called_when_snapshot_arrives():
    """_drain_snapshot_packets must call reconcile() for each new snapshot."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler(_make_snapshot_payload(nc, seq=1))

    nc._drain_snapshot_packets()

    assert len(spy.reconcile_calls) == 1
    assert spy.reconcile_calls[0].sequence_number == 1


def test_reconcile_not_called_for_stale_snapshot():
    """Snapshots with sequence_number <= last_snapshot_sequence must be discarded."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    nc.last_snapshot_sequence = 10
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler(_make_snapshot_payload(nc, seq=5))

    nc._drain_snapshot_packets()

    assert spy.reconcile_calls == []


# ---------------------------------------------------------------------------
# Noop behaviour — M4 fallback
# ---------------------------------------------------------------------------


def test_noop_reconcile_applies_snapshot_directly():
    """NoopPredictionEngine (HOST role): reconcile() sets world_state to the snapshot."""
    nc = NodeController().bootstrap(role=PlayerRole.HOST)
    snapshot_world = nc.engine.world_state.__class__(sequence_number=42)
    snapshot = WorldStateSnapshot(sequence_number=99, world_state=snapshot_world)

    nc.prediction_engine.reconcile(snapshot)

    assert nc.engine.world_state is snapshot_world


def test_noop_predict_does_not_mutate_world_state():
    """predict() on the noop must be a pure no-op with no side effects."""
    nc = NodeController().bootstrap(role=PlayerRole.HOST)
    original_seq = nc.engine.world_state.sequence_number

    nc.prediction_engine.predict(InputState(right=True))

    assert nc.engine.world_state.sequence_number == original_seq


def test_noop_should_rollback_always_returns_false():
    noop = NoopPredictionEngine()
    assert noop.should_rollback((0.0, 0.0), (999.0, 999.0)) is False


# ---------------------------------------------------------------------------
# M5 config sanity
# ---------------------------------------------------------------------------


def test_m5_config_constants_are_positive():
    assert DIVERGENCE_THRESHOLD > 0
    assert INPUT_HISTORY_SIZE > 0
    assert MAX_ROLLBACK_FRAMES > 0


def test_artificial_latency_is_zero_by_default():
    """ARTIFICIAL_LATENCY_MS must be 0 in production config."""
    assert ARTIFICIAL_LATENCY_MS == 0


def test_input_history_covers_at_least_one_second():
    """INPUT_HISTORY_SIZE frames at 60 fps must cover at least 1 s of history."""
    from distributed_smb.shared.config import TICK_RATE

    assert INPUT_HISTORY_SIZE >= TICK_RATE


def test_max_rollback_frames_less_than_history_size():
    """MAX_ROLLBACK_FRAMES must not exceed INPUT_HISTORY_SIZE."""
    assert MAX_ROLLBACK_FRAMES <= INPUT_HISTORY_SIZE
