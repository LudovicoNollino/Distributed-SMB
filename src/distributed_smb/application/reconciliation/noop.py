"""No-op implementation of PredictionEngineProtocol."""

from distributed_smb.shared.config import TICK_INTERVAL
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


class NoopPredictionEngine:
    """Passthrough — predict is a no-op, reconcile applies the snapshot directly."""

    def __init__(self) -> None:
        self._engine = None

    def predict(self, input_state: InputState, dt: float = TICK_INTERVAL) -> None:
        pass

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        if self._engine is not None:
            self._engine.world_state = authoritative_snapshot.world_state

    def should_rollback(
        self,
        predicted: tuple[float, float],
        authoritative: tuple[float, float],
    ) -> bool:
        return False

    def pending_count(self) -> int:
        return 0
