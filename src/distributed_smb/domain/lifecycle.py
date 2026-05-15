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

    def move_to_lobby(self) -> None:
        """Mark the node as waiting in the lobby/waiting room."""
        self.state = NodeState.IN_LOBBY

    def move_to_game(self) -> None:
        """Mark the node as actively running gameplay."""
        self.state = NodeState.IN_GAME

    def move_to_election(self) -> None:
        """Mark the node as resolving host migration."""
        self.state = NodeState.ELECTION

    def move_to_recovering(self) -> None:
        """Mark the node as recovering from a network/session interruption."""
        self.state = NodeState.RECOVERING

    @property
    def is_waiting_room(self) -> bool:
        return self.state is NodeState.IN_LOBBY

    @property
    def is_started(self) -> bool:
        return self.state is NodeState.IN_GAME
