"""Client-side frame synchronisation mixin."""

import logging
import time
from copy import deepcopy

from distributed_smb.shared.config import (
    PREDICTION_LEAD_DRIFT_TOLERANCE,
    PREDICTION_LEAD_EWMA_ALPHA,
    RECONCILE_GLIDE_RATE,
    RECONCILE_MAX_GLIDE_PX,
)
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.sync import WorldStateSnapshot

LOGGER = logging.getLogger(__name__)

# Number of client frames between diagnostic frame-timing log lines.
CLIENT_DIAG_LOG_INTERVAL = 120


class ClientGameplayMixin:
    def _process_client_frame(self, dt: float, local_input: InputState) -> object:
        """Run one client frame: send input, predict, tick, reconcile, drain events."""
        self._record_client_frame_interval()
        self._send_input_packet(local_input)
        self._run_predicted_ticks(dt, local_input)
        pre_reconcile_player = self.engine.world_state.get_player(self.local_player_id)
        pre_reconcile_pos = (
            (pre_reconcile_player.x, pre_reconcile_player.y)
            if pre_reconcile_player is not None
            else None
        )
        self.engine.events.clear()
        self._drain_snapshot_packets()
        self._drain_game_events()
        self._adjust_prediction_lead()
        local_visual_state = self._smoothed_local_visual_state(pre_reconcile_pos)
        return self._build_visual_world_state(local_visual_state=local_visual_state)

    def _run_predicted_ticks(self, dt: float, local_input: InputState) -> None:
        """Predict and tick the engine, applying any pending drift correction."""
        ticks = 1 + self.pending_tick_adjustment
        self.pending_tick_adjustment = 0
        for _ in range(ticks):
            self.prediction_engine.predict(local_input, dt)
            self.engine.tick(dt, {self.local_player_id: local_input})

    def _adjust_prediction_lead(self) -> None:
        """Track the prediction lead and correct clock drift against the host.

        The prediction lead (number of unacknowledged predicted ticks) tracks
        the round-trip latency in ticks and is expected to stay roughly
        constant. Client and host tick loops run at very slightly different
        real-world rates, so the lead drifts steadily if left uncorrected.

        During the first PREDICTION_LEAD_CALIBRATION_FRAMES frames, the
        baseline is settled onto the connection's true lead via EWMA. After
        that it is frozen: deviations from this fixed baseline trigger a
        one-tick correction (skip a tick if running ahead, double-tick if
        running behind) for the next frame, which cancels the clock-rate
        mismatch instead of letting the baseline drift along with it.
        """
        pending = self.prediction_engine.pending_count()
        baseline = self.prediction_lead_baseline or float(pending)
        deviation = pending - baseline

        if deviation > PREDICTION_LEAD_DRIFT_TOLERANCE:
            self.pending_tick_adjustment = -1
            LOGGER.info(
                "prediction lead drift: pending=%d baseline=%.2f -> skipping next tick",
                pending,
                baseline,
            )
        elif deviation < -PREDICTION_LEAD_DRIFT_TOLERANCE:
            self.pending_tick_adjustment = 1
            LOGGER.info(
                "prediction lead drift: pending=%d baseline=%.2f -> double-ticking next frame",
                pending,
                baseline,
            )
        elif self.prediction_lead_calibration_remaining > 0:
            baseline += (pending - baseline) * PREDICTION_LEAD_EWMA_ALPHA

        if self.prediction_lead_calibration_remaining > 0:
            self.prediction_lead_calibration_remaining -= 1

        self.prediction_lead_baseline = baseline

    def _smoothed_local_visual_state(self, pre_reconcile_pos: tuple[float, float] | None):
        """Absorb the reconciliation correction gradually instead of snapping.

        reconcile() may have moved the local player (rollback + replay). Render
        a position that continues smoothly from last frame and closes the
        accumulated error toward the authoritative position at a rate
        proportional to the outstanding error (RECONCILE_GLIDE_RATE), capped
        at RECONCILE_MAX_GLIDE_PX per frame. Small errors (a few px of normal
        prediction jitter) resolve in 1-2 frames; large errors (a jump-timing
        mismatch, tens of px) resolve in a handful of frames at the capped
        rate instead of lingering for a full second, which would let the
        backlog pile up if corrections recur faster than that.
        """
        player = self.engine.world_state.get_player(self.local_player_id)
        if player is None or pre_reconcile_pos is None:
            return player

        correction_x = player.x - pre_reconcile_pos[0]
        correction_y = player.y - pre_reconcile_pos[1]
        offset_x, offset_y = self.visual_correction_offset
        offset_x += correction_x
        offset_y += correction_y

        glide_x = self._glide_step(offset_x)
        glide_y = self._glide_step(offset_y)
        offset_x -= glide_x
        offset_y -= glide_y
        self.visual_correction_offset = (offset_x, offset_y)

        visual_player = deepcopy(player)
        visual_player.x -= offset_x
        visual_player.y -= offset_y
        return visual_player

    @staticmethod
    def _glide_step(offset: float) -> float:
        step = offset * RECONCILE_GLIDE_RATE
        return max(-RECONCILE_MAX_GLIDE_PX, min(RECONCILE_MAX_GLIDE_PX, step))

    def _record_client_frame_interval(self) -> None:
        """Track wall-clock time between consecutive client frames."""
        now = time.monotonic()
        if self.client_last_frame_at is not None:
            self.client_frame_intervals.append(now - self.client_last_frame_at)
        self.client_last_frame_at = now

        if len(self.client_frame_intervals) < CLIENT_DIAG_LOG_INTERVAL:
            return
        intervals = self.client_frame_intervals
        avg_ms = sum(intervals) / len(intervals) * 1000.0
        min_ms = min(intervals) * 1000.0
        max_ms = max(intervals) * 1000.0
        LOGGER.info(
            "client frame stats: interval_ms avg=%.2f min=%.2f max=%.2f pending=%d baseline=%.2f",
            avg_ms,
            min_ms,
            max_ms,
            self.prediction_engine.pending_count(),
            self.prediction_lead_baseline,
        )
        self.client_frame_intervals.clear()

    def _drain_snapshot_packets(self) -> None:
        """Poll incoming snapshots, reconcile predicted state, update shadow copies."""
        while True:
            packet = self.udp_handler.receive_packet_nowait()
            if packet is None:
                return
            payload, _address = packet
            decoded = self.serializer.decode_message(payload)
            if not isinstance(decoded, WorldStateSnapshot):
                continue
            if decoded.sequence_number <= self.last_snapshot_sequence:
                continue

            self.last_snapshot_sequence = decoded.sequence_number
            self.prediction_engine.reconcile(decoded)
            self._update_shadow_copies(decoded)
            self.received_snapshots += 1

    def _update_shadow_copies(self, snapshot: WorldStateSnapshot) -> None:
        """Push new authoritative states to shadow copies for all remote players."""
        for pid, char_state in snapshot.world_state.characters.items():
            if pid == self.local_player_id:
                continue
            shadow = self.shadow_copies.get(pid)
            if shadow is None:
                shadow = self.shadow_copy_factory()
                self.shadow_copies[pid] = shadow
            shadow.update(char_state)

    def _send_input_packet(self, local_input: InputState) -> None:
        """Send the local client's input packet to the authoritative host."""
        self.input_sequence_number += 1
        packet = PlayerInputPacket(
            player_id=self.local_player_id,
            sequence_number=self.input_sequence_number,
            input_state=local_input,
        )
        payload = self.serializer.encode_message(packet)
        self.udp_handler.send_packet_nowait(payload, self.remote_host, self.remote_port)
        self.sent_input_packets += 1
