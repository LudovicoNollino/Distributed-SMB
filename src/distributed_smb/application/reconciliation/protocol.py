"""Protocol definition for client-side prediction and reconciliation."""

from typing import Protocol, runtime_checkable

from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot


@runtime_checkable
class PredictionEngineProtocol(Protocol):
    """Encapsulates client-side prediction, input buffering, and reconciliation."""

    def predict(self, input_state: InputState, dt: float) -> None:
        """Buffer the input under the next sequence number, before the local tick."""

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        """Adopt the authoritative state and replay the still-unacknowledged inputs."""

    def pending_count(self) -> int:
        """Return the number of unacknowledged predicted inputs still buffered."""
