"""Node lifecycle state machine."""

from dataclasses import dataclass

from distributed_smb.shared.enums import NodeState


@dataclass(slots=True)
class NodeLifecycle:
    """Tracks the current operating mode of the node."""

    state: NodeState = NodeState.IDLE

    def move_to_idle(self) -> None:
        """Reset the node to the idle state."""
        self.state = NodeState.IDLE
