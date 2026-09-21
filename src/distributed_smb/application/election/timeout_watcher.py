"""Host failure detector using timeout-based heartbeat monitoring."""


class HostTimeoutWatcher:
    """Tracks the last WorldStateSnapshot timestamp and detects timeout."""

    def __init__(self, timeout_s: float):
        """Initialize the watcher."""
        self.timeout_s = timeout_s
        self.last_snapshot_time: float | None = None

    def reset(self, timestamp: float) -> None:
        """Record receipt of a new WorldStateSnapshot."""
        self.last_snapshot_time = timestamp

    def tick(self, current_time: float) -> bool:
        """Check if host has timed out."""
        if self.last_snapshot_time is None:
            return False
        return (current_time - self.last_snapshot_time) > self.timeout_s
