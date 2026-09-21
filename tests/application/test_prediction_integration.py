"""Prediction and reconciliation wiring inside the node controller."""

from distributed_smb.application.node_controller import NodeController
from distributed_smb.application.reconciliation import (
    NoopPredictionEngine,
    PredictionEngine,
)
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.config import (
    TICK_INTERVAL,
)
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


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
        self.predict_dts: list[float] = []
        self.reconcile_calls: list[WorldStateSnapshot] = []

    def predict(self, input_state: InputState, dt: float) -> None:
        self.predict_calls.append(input_state)
        self.predict_dts.append(dt)

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        self.reconcile_calls.append(authoritative_snapshot)

    def pending_count(self) -> int:
        return 0


def _make_snapshot_payload(nc: NodeController, seq: int = 1) -> bytes:
    return Serializer().encode_message(
        WorldStateSnapshot(sequence_number=seq, world_state=nc.engine.world_state)
    )


def test_bootstrap_wires_the_engine_by_role_and_keeps_an_injected_one():
    """Only the client predicts; the host is authoritative and never needs to."""
    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    assert isinstance(client.prediction_engine, PredictionEngine)
    assert client.prediction_engine.engine is client.engine
    assert client.prediction_engine.local_player_id == client.local_player_id

    host = NodeController().bootstrap(role=PlayerRole.HOST)
    assert isinstance(host.prediction_engine, NoopPredictionEngine)
    # The host reconciles only when bootstrapping from someone else's snapshot,
    # and then it takes it whole.
    snapshot_world = host.engine.world_state.__class__(sequence_number=42)
    host.prediction_engine.reconcile(
        WorldStateSnapshot(sequence_number=99, world_state=snapshot_world)
    )
    assert host.engine.world_state is snapshot_world

    spy = _SpyPredictionEngine()
    assert NodeController(prediction_engine=spy).prediction_engine is spy


def test_predict_runs_once_per_client_frame_and_never_on_the_host():
    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    client_spy = _SpyPredictionEngine()
    client.prediction_engine = client_spy
    client.udp_handler = _FakeUdpHandler()
    input_state = InputState(right=True)

    client.process_frame(input_state)

    assert client_spy.predict_calls == [input_state]

    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host_spy = _SpyPredictionEngine()
    host.prediction_engine = host_spy
    host.udp_handler = _FakeUdpHandler()

    host.process_frame(InputState())

    assert host_spy.predict_calls == []


def test_every_predicted_tick_uses_the_fixed_simulation_step():
    """However long the real frame took, the tick is integrated by
    TICK_INTERVAL: a tick replayed with a different step than the host used
    for it lands somewhere else, and the error compounds over a jump arc."""
    nc = NodeController().bootstrap(role=PlayerRole.CLIENT)
    spy = _SpyPredictionEngine()
    nc.prediction_engine = spy
    nc.udp_handler = _FakeUdpHandler()

    nc.process_frame(InputState(right=True))

    assert spy.predict_dts == [TICK_INTERVAL]


def test_reconcile_runs_for_a_new_snapshot_and_is_skipped_for_a_stale_one():
    """An out-of-order snapshot would rewind the client to an older state."""
    fresh = NodeController().bootstrap(role=PlayerRole.CLIENT)
    spy = _SpyPredictionEngine()
    fresh.prediction_engine = spy
    fresh.udp_handler = _FakeUdpHandler(_make_snapshot_payload(fresh, seq=1))

    fresh._drain_snapshot_packets()

    assert len(spy.reconcile_calls) == 1
    assert spy.reconcile_calls[0].sequence_number == 1

    ahead = NodeController().bootstrap(role=PlayerRole.CLIENT)
    ahead.last_snapshot_sequence = 10
    stale_spy = _SpyPredictionEngine()
    ahead.prediction_engine = stale_spy
    ahead.udp_handler = _FakeUdpHandler(_make_snapshot_payload(ahead, seq=5))

    ahead._drain_snapshot_packets()

    assert stale_spy.reconcile_calls == []
