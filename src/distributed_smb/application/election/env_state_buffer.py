"""Buffer for the most recent WorldStateSnapshot received via UDP."""

from distributed_smb.shared.messages.sync import WorldStateSnapshot


class EnvironmentalStateBuffer:
    """Single-slot buffer for the last received WorldStateSnapshot."""

    def __init__(self) -> None:
        self._last: WorldStateSnapshot | None = None

    def update(self, snapshot: WorldStateSnapshot) -> None:
        """Replace the stored snapshot with the latest one."""
        self._last = snapshot

    def get_last(self) -> WorldStateSnapshot | None:
        """Return the last stored snapshot, or None if none received yet."""
        return self._last
