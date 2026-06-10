"""Client-side frame synchronisation mixin."""

import logging

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
        local_visual_state = self.engine.world_state.get_player(self.local_player_id)
        self.engine.events.clear()
        self._drain_snapshot_packets()
        self._drain_game_events()
        return self._build_visual_world_state(local_visual_state=local_visual_state)

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
