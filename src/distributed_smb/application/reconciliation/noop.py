"""No-op implementation of PredictionEngineProtocol.

Used as default in NodeController before Persona 1 delivers the real
PredictionEngine. Behavioural contract: identical to M4 — snapshot is
applied directly, no rollback, no input replay.
"""

from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


class NoopPredictionEngine:
    """Passthrough — predict and reconcile are no-ops, rollback never triggers."""

    def predict(self, input_state: InputState) -> None:
        pass

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        pass

    def should_rollback(
        self,
        predicted: tuple[float, float],
        authoritative: tuple[float, float],
    ) -> bool:
        return False
