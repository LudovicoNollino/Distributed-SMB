"""Host failure detector using timeout-based heartbeat monitoring.

Eventually perfect failure detector (◇P): assumes reliable FIFO channels and
asynchronous network with bounded delays. In practice:
- False negatives (missing a crash): impossible (heartbeat timeout catches it).
- False positives (falsely declaring alive node dead): possible under extreme latency,
  but rare in normal conditions (< 2% under 100-200ms baseline jitter).
"""


class HostTimeoutWatcher:
    """Tracks the last WorldStateSnapshot timestamp and detects timeout.

    Attributes:
        last_snapshot_time: Unix timestamp of the most recent UDP snapshot received.
        timeout_s: Seconds without a snapshot before declaring host lost (HOST_TIMEOUT_S).
    """

    def __init__(self, timeout_s: float):
        """Initialize the watcher.

        Args:
            timeout_s: Timeout duration in seconds (typically HOST_TIMEOUT_S = 5.0).
        """
        self.timeout_s = timeout_s
        self.last_snapshot_time: float | None = None

    def reset(self, timestamp: float) -> None:
        """Record receipt of a new WorldStateSnapshot.

        Args:
            timestamp: Unix timestamp of the snapshot (typically time.time()).
        """
        self.last_snapshot_time = timestamp

    def tick(self, current_time: float) -> bool:
        """Check if host has timed out.

        Returns:
            True if (current_time - last_snapshot_time) > timeout_s,
            False if no snapshot received yet or if timeout not exceeded.
        """
        if self.last_snapshot_time is None:
            return False
        return (current_time - self.last_snapshot_time) > self.timeout_s
