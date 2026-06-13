"""Protocol definition for client-side prediction and reconciliation."""

from typing import Protocol, runtime_checkable

from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


@runtime_checkable
class PredictionEngineProtocol(Protocol):
    """Encapsulates client-side prediction, input buffering, and reconciliation."""

    def predict(self, input_state: InputState, dt: float) -> None:
        """Record the input, dt and snapshot the current engine state before the tick."""

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        """Compare the snapshot with the buffered predicted state.

        If divergence exceeds DIVERGENCE_THRESHOLD, rolls back to the
        authoritative state and replays all unacknowledged inputs.
        """

    def should_rollback(
        self,
        predicted: tuple[float, float],
        authoritative: tuple[float, float],
    ) -> bool:
        """Return True if euclidean distance between positions exceeds the threshold."""

    def pending_count(self) -> int:
        """Return the number of unacknowledged predicted inputs still buffered."""
