"""Visual smoothing for remote entities received through snapshots."""

from dataclasses import dataclass, replace

from distributed_smb.domain.world import CharacterState
from distributed_smb.shared.config import MAX_EXTRAPOLATION_TIME, SNAPSHOT_TIMEOUT


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _lerp(start: float, end: float, alpha: float) -> float:
    return start + (end - start) * alpha


@dataclass(slots=True)
class ShadowCopy:
    """Maintain a smoothed visual state for a single remote entity."""

    snapshot_timeout: float = SNAPSHOT_TIMEOUT
    max_extrapolation_time: float = MAX_EXTRAPOLATION_TIME
    last_confirmed: CharacterState | None = None
    target: CharacterState | None = None
    last_sequence_number: int = -1
    last_snapshot_time: float | None = None
    interpolation_window: float = SNAPSHOT_TIMEOUT

    def update(
        self,
        new_snapshot: CharacterState,
        *,
        sequence_number: int,
        received_at: float,
    ) -> bool:
        """Store the newest authoritative snapshot if it is not out of order."""
        if sequence_number <= self.last_sequence_number:
            return False

        snapshot = replace(new_snapshot)
        previous_snapshot_time = self.last_snapshot_time

        if self.target is None:
            self.last_confirmed = replace(snapshot)
            self.target = snapshot
            self.interpolation_window = self.snapshot_timeout
        else:
            self.last_confirmed = replace(self.target)
            self.target = snapshot
            if previous_snapshot_time is None:
                self.interpolation_window = self.snapshot_timeout
            else:
                delta = received_at - previous_snapshot_time
                self.interpolation_window = max(
                    1e-6,
                    min(self.snapshot_timeout, delta),
                )

        self.last_sequence_number = sequence_number
        self.last_snapshot_time = received_at
        return True

    def interpolate(self, alpha: float) -> CharacterState:
        """Return a visual state linearly interpolated between snapshots."""
        if self.target is None:
            raise ValueError("Cannot interpolate without at least one snapshot")

        start = self.last_confirmed or self.target
        alpha = _clamp(alpha, 0.0, 1.0)
        return replace(
            self.target,
            x=_lerp(start.x, self.target.x, alpha),
            y=_lerp(start.y, self.target.y, alpha),
            vx=_lerp(start.vx, self.target.vx, alpha),
            vy=_lerp(start.vy, self.target.vy, alpha),
            prev_x=_lerp(start.prev_x, self.target.prev_x, alpha),
            prev_y=_lerp(start.prev_y, self.target.prev_y, alpha),
        )

    def get_visual_state(self, now: float) -> CharacterState | None:
        """Return the current smoothed visual state for rendering."""
        if self.target is None:
            return None
        if self.last_snapshot_time is None:
            return replace(self.target)

        elapsed = max(0.0, now - self.last_snapshot_time)
        if elapsed <= self.snapshot_timeout:
            alpha = elapsed / self.interpolation_window
            return self.interpolate(alpha)

        extrapolation_elapsed = min(
            elapsed - self.snapshot_timeout,
            self.max_extrapolation_time,
        )
        stopped = elapsed - self.snapshot_timeout >= self.max_extrapolation_time
        return replace(
            self.target,
            x=self.target.x + self.target.vx * extrapolation_elapsed,
            y=self.target.y + self.target.vy * extrapolation_elapsed,
            prev_x=self.target.prev_x + self.target.vx * extrapolation_elapsed,
            prev_y=self.target.prev_y + self.target.vy * extrapolation_elapsed,
            vx=0.0 if stopped else self.target.vx,
            vy=0.0 if stopped else self.target.vy,
        )
