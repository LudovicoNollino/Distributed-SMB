"""Protocol definition for client-side prediction and reconciliation.

Defines the contract that Persona 1's PredictionEngine must satisfy.
ClientGameplayMixin depends only on this protocol — swapping in the
real implementation requires no changes to the caller.
"""

from typing import Protocol, runtime_checkable

from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


@runtime_checkable
class PredictionEngineProtocol(Protocol):
    """Encapsulates client-side prediction, input buffering, and reconciliation."""

    def predict(self, input_state: InputState, dt: float) -> None:
        """Record the input, dt and snapshot the current engine state before the tick.

        NOTE: does NOT call engine.tick() — the caller is responsible for
        ticking the engine after this call. This avoids double-tick when
        the real implementation is wired in. dt is recorded so that
        reconcile() can replay this input with the same step size used
        for the original live tick.
        """
        ...

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        """Compare the snapshot with the buffered predicted state.

        If divergence exceeds DIVERGENCE_THRESHOLD, rolls back to the
        authoritative state and replays all unacknowledged inputs.
        """
        ...

    def should_rollback(
        self,
        predicted: tuple[float, float],
        authoritative: tuple[float, float],
    ) -> bool:
        """Return True if euclidean distance between positions exceeds the threshold."""
        ...

    def pending_count(self) -> int:
        """Return the number of unacknowledged predicted inputs still buffered."""
        ...
