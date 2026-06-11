"""Client-side frame synchronisation mixin."""

import logging
from copy import deepcopy

from distributed_smb.shared.config import RECONCILE_SMOOTHING_DECAY
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.sync import WorldStateSnapshot

LOGGER = logging.getLogger(__name__)


class ClientGameplayMixin:
    def _process_client_frame(self, dt: float, local_input: InputState) -> object:
        """Run one client frame: send input, predict, tick, reconcile, drain events."""
        self._send_input_packet(local_input)
        self.prediction_engine.predict(local_input, dt)
        self.engine.tick(dt, {self.local_player_id: local_input})
        pre_reconcile_player = self.engine.world_state.get_player(self.local_player_id)
        pre_reconcile_pos = (
            (pre_reconcile_player.x, pre_reconcile_player.y)
            if pre_reconcile_player is not None
            else None
        )
        self.engine.events.clear()
        self._drain_snapshot_packets()
        self._drain_game_events()
        local_visual_state = self._smoothed_local_visual_state(pre_reconcile_pos)
        return self._build_visual_world_state(local_visual_state=local_visual_state)

    def _smoothed_local_visual_state(self, pre_reconcile_pos: tuple[float, float] | None):
        """Absorb the reconciliation correction gradually instead of snapping.

        reconcile() may have moved the local player (rollback + replay). Render
        a position that continues smoothly from last frame and decays the
        accumulated error toward the authoritative position over time.
        """
        player = self.engine.world_state.get_player(self.local_player_id)
        if player is None or pre_reconcile_pos is None:
            return player

        correction_x = player.x - pre_reconcile_pos[0]
        correction_y = player.y - pre_reconcile_pos[1]
        offset_x, offset_y = self.visual_correction_offset
        offset_x = offset_x * RECONCILE_SMOOTHING_DECAY + correction_x
        offset_y = offset_y * RECONCILE_SMOOTHING_DECAY + correction_y
        self.visual_correction_offset = (offset_x, offset_y)

        visual_player = deepcopy(player)
        visual_player.x -= offset_x
        visual_player.y -= offset_y
        return visual_player

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
