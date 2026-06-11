"""No-op implementation of PredictionEngineProtocol.

Used as default in NodeController before Persona 1 delivers the real
PredictionEngine. Behavioural contract: identical to M4 — snapshot is
applied directly, no rollback, no input replay.

NodeController.__post_init__ sets _engine so reconcile() can apply
the snapshot without a separate engine reference at construction time.
"""

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
