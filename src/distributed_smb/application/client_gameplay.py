"""Client-side frame synchronisation mixin."""

import logging
import time
from copy import deepcopy

from distributed_smb.application.election import (
    ElectionCoordinator,
    EnvironmentalStateBuffer,
    HostTimeoutWatcher,
    SelfElected,
)
from distributed_smb.shared.config import (
    GAME_EVENT_WS_PATH,
    GAME_EVENT_WS_PORT,
    HOST_TIMEOUT_S,
    HOST_UDP_PORT,
    HOST_VERIFY_RESEND_INTERVAL_S,
    HOST_VERIFY_TIMEOUT_S,
    PREDICTION_LEAD_CALIBRATION_FRAMES,
    PREDICTION_LEAD_DRIFT_TOLERANCE,
    PREDICTION_LEAD_EWMA_ALPHA,
    RECONCILE_GLIDE_RATE,
    RECONCILE_MAX_GLIDE_PX,
    RECONNECTION_FALLBACK_TIMEOUT_S,
    T_ELECTION_BASE_S,
    T_ELECTION_DELTA_S,
    TICK_INTERVAL,
)
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.election import (
    ElectionAck,
    ElectionNack,
    NewHostClaim,
    ReconnectionAck,
)
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.recovery import HostDiscoveryProbe, HostIdentityResponse
from distributed_smb.shared.messages.sync import InitialStateSync, WorldStateSnapshot
from distributed_smb.shared.session_metadata import CachedPeer

LOGGER = logging.getLogger(__name__)

# Number of client frames between diagnostic frame-timing log lines.
CLIENT_DIAG_LOG_INTERVAL = 120


class ClientGameplayMixin:
    def _process_client_frame(self, dt: float, local_input: InputState) -> object:
        """Run one client frame: send input, predict, tick, reconcile, drain events."""
        self._ensure_election_components()
        self._record_client_frame_interval()
        self._drain_lobby_messages()
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
        self._tick_election_state()
        self._adjust_prediction_lead()
        local_visual_state = self._smoothed_local_visual_state(pre_reconcile_pos)
        return self._build_visual_world_state(local_visual_state=local_visual_state)

    # ------------------------------------------------------------------
    # Election lifecycle
    # ------------------------------------------------------------------

    def _ensure_election_components(self) -> None:
        """Lazy-init election components on first client frame (roster available here)."""
        if self.election_coordinator is not None:
            return
        entry = self.roster.get_player(self.local_player_id)
        if entry is not None:
            self.join_index = entry.join_index
        self.election_coordinator = ElectionCoordinator(
            join_index=self.join_index,
            my_ip=self.local_ip,
            timeout_base_s=T_ELECTION_BASE_S,
            timeout_delta_s=T_ELECTION_DELTA_S,
        )
        self.timeout_watcher = HostTimeoutWatcher(timeout_s=HOST_TIMEOUT_S)
        self.env_state_buffer = EnvironmentalStateBuffer()

    def _known_client_peers(self) -> set[str]:
        """IPs of all surviving peers (excluding the crashed host and self)."""
        return {
            entry.host
            for entry in self.roster.get_all_players()
            if not entry.is_host and entry.player_id != self.local_player_id
        }

    def _tick_election_state(self) -> None:
        """Check host timeout and advance the election state machine."""
        if self.election_coordinator is None or self.timeout_watcher is None:
            return

        now = time.time()

        if self._host_verify_deadline == 0.0:
            if not self.election_triggered and self.timeout_watcher.tick(now):
                LOGGER.warning("host timeout suspected — verifying before starting election")
                self._send_host_verify_probe(now)
        else:
            self._tick_host_verify(now)

        if self.election_triggered:
            event = self.election_coordinator.tick(now)
            if isinstance(event, SelfElected):
                LOGGER.info("election: self-elected as new host (ip=%s)", event.my_ip)
                self._on_self_elected(event)
            self._tick_claim_deadline(now)
            self._tick_reconnection_fallback(now)

    def _send_host_verify_probe(self, now: float) -> None:
        """Probe the suspected-dead host directly before trusting the local timeout.

        A snapshot gap can come from a brief stall (GC pause, CPU contention
        from other peers/containers sharing the machine, a network blip)
        rather than an actual crash — observed in testing as a multi-second
        game-loop freeze on an otherwise-healthy peer, immediately after a
        migration, with no corresponding freeze on the real host. Confirming
        via a direct probe avoids cascading into a false, conflicting
        election off the back of that kind of transient delay.
        """
        self._host_verify_deadline = now + HOST_VERIFY_TIMEOUT_S
        self._host_verify_next_probe = now
        self._resend_host_verify_probe(now)

    def _resend_host_verify_probe(self, now: float) -> None:
        self._host_verify_next_probe = now + HOST_VERIFY_RESEND_INTERVAL_S
        probe = HostDiscoveryProbe(session_id=self.session_id, requester_ip=self.local_ip)
        self.udp_handler.send_packet_nowait(
            self.serializer.encode_message(probe), self.remote_host, self.remote_port
        )

    def _tick_host_verify(self, now: float) -> None:
        if not self.timeout_watcher.tick(now):
            # A fresh snapshot (or a verify response, see _on_host_identity_response)
            # arrived while we were waiting — the host is alive after all.
            self._host_verify_deadline = 0.0
            return
        if now >= self._host_verify_deadline:
            LOGGER.warning("host timeout confirmed — starting election")
            self._host_verify_deadline = 0.0
            self.election_triggered = True
            peers = self._known_client_peers()
            self.election_coordinator.start_election(peers)
            self.election_coordinator.set_election_timer(now)
            return
        if now >= self._host_verify_next_probe:
            self._resend_host_verify_probe(now)

    def _on_host_identity_response(self, msg: HostIdentityResponse) -> None:
        if self._host_verify_deadline == 0.0:
            return
        if msg.session_id != self.session_id:
            return
        LOGGER.info("election: host verify probe answered — host alive, election cancelled")
        self._host_verify_deadline = 0.0
        if self.timeout_watcher is not None:
            self.timeout_watcher.reset(time.time())

    def _tick_reconnection_fallback(self, now: float) -> None:
        """Fall back to a direct UDP probe if ReconnectionAck never arrives.

        ReconnectionAck normally relays through the crashed host's own relay
        container — if that container went down with the host (e.g. a clean
        shutdown that also stops it), a following peer would wait forever.
        RecoveryProber talks UDP directly to the claimed candidate instead.
        """
        if self.reconnected or self._following_host_ip is None:
            return
        if now - self._following_since < RECONNECTION_FALLBACK_TIMEOUT_S:
            return

        candidate_ip = self._following_host_ip
        # The candidate's own promotion (Docker containers, WS retries) can take
        # much longer than one probe timeout — retry every interval instead of
        # giving up after a single miss.
        self._following_since = now
        LOGGER.warning(
            "election: no ReconnectionAck from %s after %.1fs — probing directly",
            candidate_ip,
            RECONNECTION_FALLBACK_TIMEOUT_S,
        )
        found_ip = self.recovery_prober.find_current_host(
            self.session_id,
            self.local_ip,
            [CachedPeer(player_id="", ip=candidate_ip, join_index=-1)],
            timeout_per_peer=1.5,
        )
        if found_ip is None:
            LOGGER.warning(
                "election: direct probe to %s got no response — will retry", candidate_ip
            )
            return
        self._following_host_ip = None
        self._on_reconnection_ack(
            ReconnectionAck(
                new_host_ip=found_ip,
                udp_port=HOST_UDP_PORT,
                game_events_port=GAME_EVENT_WS_PORT,
                session_id=self.session_id,
            )
        )

    # ------------------------------------------------------------------
    # Election event handlers (called from _drain_game_events)
    # ------------------------------------------------------------------

    def _on_election_nack(self, msg: ElectionNack) -> None:
        pass

    def _on_reconnection_ack(self, ack: ReconnectionAck) -> None:
        if self.reconnected or self._promotion_done:
            return
        self.reconnected = True
        self.remote_host = ack.new_host_ip
        self.remote_port = ack.udp_port
        self._reconnect_game_event_handler(
            ack.new_host_ip, ack.game_events_port, GAME_EVENT_WS_PATH
        )
        self.game_event_broker.reconnect(ack.new_host_ip, ack.game_events_port)
        self._reconnect_lobby_ws_handler(ack.new_host_ip)
        LOGGER.info(
            "reconnected to new host %s (udp_port=%d, game_events_port=%d)",
            ack.new_host_ip,
            ack.udp_port,
            ack.game_events_port,
        )

        # Resync locally-predicted environment state (destructible blocks,
        # power-ups, cooperative gates) against the last known-good pre-crash
        # snapshot. reconcile() deliberately never overwrites these three
        # fields from an authoritative snapshot (see M4) to avoid visual
        # pop-in when this node predicts a block break locally — but that
        # also means a BlockDestroyedMessage/game event lost during the
        # crash window (the WS relay can die with the old host) leaves this
        # node's local copy permanently diverged from every other survivor.
        # The newly promoted host restores this exact same buffered snapshot
        # via bootstrap_from_snapshot(); applying it here too keeps every
        # surviving client in agreement with it at the moment of migration.
        if self.env_state_buffer is not None:
            last = self.env_state_buffer.get_last()
            if last is not None:
                env = last.world_state.environment
                self.engine.world_state.environment.destructible_blocks = env.destructible_blocks
                self.engine.world_state.environment.power_ups = env.power_ups
                self.engine.world_state.environment.cooperative_gates = env.cooperative_gates

        # The new host resumes from its own last buffered snapshot, whose sequence
        # can be lower than the last one this client saw — without this reset every
        # snapshot from it would be discarded as stale and never reconciled.
        self.last_snapshot_sequence = 0

        # Sync local roster: evict the crashed host and promote the newly elected one.
        # Without this, _known_client_peers() would still see the old host as a peer
        # and _promote_to_host() would evict the wrong entry in any future election.
        old_host = self.roster.get_host()
        if old_host is not None:
            self._evict_player(old_host.player_id)
        new_host_entry = next(
            (e for e in self.roster.get_all_players() if e.host == ack.new_host_ip), None
        )
        if new_host_entry is not None:
            self.roster.promote_host(new_host_entry.player_id)

        # Reset the election machinery so a future host crash triggers a fresh election.
        # election_triggered stays True after a follow, which silently swallows the second
        # timeout check and prevents the node from ever detecting a subsequent crash.
        self.election_triggered = False
        self._pending_election_acks = set()
        self._election_claim_deadline = 0.0
        self.election_coordinator = None  # lazily re-created in _ensure_election_components
        self.timeout_watcher = HostTimeoutWatcher(timeout_s=HOST_TIMEOUT_S)
        self._host_verify_deadline = 0.0

        # Reset prediction-lead calibration for the new host. The baseline was frozen
        # against the old host's RTT; the new host may be on a different machine with
        # a different round-trip time, which would produce a permanent deviation and
        # cause sustained reconciliation corrections and visible jitter.
        self.prediction_lead_baseline = 0.0
        self.prediction_lead_calibration_remaining = PREDICTION_LEAD_CALIBRATION_FRAMES
        self.visual_correction_offset = (0.0, 0.0)

    def _drain_lobby_messages(self) -> None:
        """Drain lobby WS messages during gameplay — handles InitialStateSync on rejoin."""
        while True:
            msg = self.ws_handler.poll()
            if msg is None:
                break
            if isinstance(msg, InitialStateSync):
                self.engine.world_state = msg.world_state
                self.last_snapshot_sequence = self.engine.world_state.sequence_number
                LOGGER.info(
                    "rejoin: applied InitialStateSync (seq=%d)",
                    self.engine.world_state.sequence_number,
                )

    # ------------------------------------------------------------------
    # Prediction and reconciliation
    # ------------------------------------------------------------------

    def _run_predicted_ticks(self, dt: float, local_input: InputState) -> None:
        """Predict and tick the engine, applying any pending drift correction."""
        ticks = 1 + self.pending_tick_adjustment
        self.pending_tick_adjustment = 0
        # Fixed simulation step, not the real (variable) frame dt: apply_physics()
        # integrates gravity/velocity as GRAVITY*dt and vy*dt. _replay_pending()
        # later re-ticks these same buffered inputs against the authoritative
        # host's own ticks for the same sequence numbers — if this client used
        # a different dt than the host did for "the same" tick (near-certain
        # with two independently wall-clock-timed frame loops, especially
        # under CPU contention), the two diverge, compounding over a jump arc
        # into the large, frequent reconciliation corrections seen in testing.
        for _ in range(ticks):
            self.prediction_engine.predict(local_input, TICK_INTERVAL)
            self.engine.tick(TICK_INTERVAL, {self.local_player_id: local_input})

    def _adjust_prediction_lead(self) -> None:
        """Track the prediction lead and correct clock drift against the host."""
        pending = self.prediction_engine.pending_count()
        baseline = self.prediction_lead_baseline
        deviation = pending - baseline

        if deviation > PREDICTION_LEAD_DRIFT_TOLERANCE:
            self.pending_tick_adjustment = -1
            baseline += 1.0
            LOGGER.debug(
                "prediction lead drift: pending=%d baseline=%.2f -> skipping next tick",
                pending,
                baseline,
            )
        elif deviation < -PREDICTION_LEAD_DRIFT_TOLERANCE:
            self.pending_tick_adjustment = 1
            baseline -= 1.0
            LOGGER.debug(
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
        """Absorb the reconciliation correction gradually instead of snapping."""
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
        """Poll incoming snapshots, reconcile predicted state, update shadow copies.

        Also dispatches election/reconnection messages arriving here — these
        travel over direct UDP (in addition to the WS relay) so surviving
        peers can coordinate a host migration even if the relay is down.
        """
        now = time.time()
        while True:
            packet = self.udp_handler.receive_packet_nowait()
            if packet is None:
                return
            payload, _address = packet
            decoded = self.serializer.decode_message(payload)

            if isinstance(decoded, NewHostClaim):
                self._on_new_host_claim(decoded)
                continue
            if isinstance(decoded, ElectionAck):
                self._on_election_ack(decoded)
                continue
            if isinstance(decoded, ReconnectionAck):
                self._on_reconnection_ack(decoded)
                continue
            if isinstance(decoded, HostIdentityResponse):
                self._on_host_identity_response(decoded)
                continue
            if not isinstance(decoded, WorldStateSnapshot):
                continue
            if decoded.sequence_number <= self.last_snapshot_sequence:
                continue

            self.last_snapshot_sequence = decoded.sequence_number
            self.prediction_engine.reconcile(decoded)
            self._update_shadow_copies(decoded)
            self.received_snapshots += 1
            if self.timeout_watcher is not None:
                self.timeout_watcher.reset(now)
            if self.env_state_buffer is not None:
                self.env_state_buffer.update(decoded)

    def _update_shadow_copies(self, snapshot: WorldStateSnapshot) -> None:
        """Push new authoritative states to shadow copies for all remote players."""
        for pid, char_state in snapshot.world_state.characters.items():
            if pid == self.local_player_id:
                continue
            shadow = self.shadow_copies.get(pid)
            if shadow is None:
                shadow = self.shadow_copy_factory()
                self.shadow_copies[pid] = shadow
            shadow.update(char_state, snapshot.sequence_number)

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
