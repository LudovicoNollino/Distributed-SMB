"""Buffer for the most recent WorldStateSnapshot received via UDP.

Keeps the last snapshot seen by the node (host or client). When a host
timeout is detected, this buffer holds the state immediately preceding the
crash, which the newly elected host applies as its authoritative starting
point via bootstrap_from_snapshot().

No explicit state transfer protocol is needed: each client already has an
up-to-date copy of the world via UDP snapshots, so the buffer is simply
the last packet received.
"""

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
