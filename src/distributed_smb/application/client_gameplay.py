"""Client-side frame synchronisation mixin.

M5 insertion points:
  - _process_client_frame: predict() before tick, reconcile() on snapshot
  - _drain_snapshot_packets: shadow copy updated on every new snapshot
  - _get_display_world_state: interpolated remote positions passed to Renderer
"""

import logging

from distributed_smb.domain.world import WorldState
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.sync import WorldStateSnapshot

LOGGER = logging.getLogger(__name__)


class ClientGameplayMixin:
    def _process_client_frame(self, dt: float, local_input: InputState) -> object:
        """Run one client frame: send input, predict, tick, reconcile, drain events."""
        self._send_input_packet(local_input)
        self.prediction_engine.predict(local_input)
        self.engine.tick(dt, {self.local_player_id: local_input})
        self.engine.events.clear()
        self._drain_snapshot_packets()
        self._drain_game_events()
        return self._get_display_world_state()

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
        for pid, shadow in self.shadow_copies.items():
            char_state = snapshot.world_state.characters.get(pid)
            if char_state is not None:
                shadow.update(char_state)

    def _get_display_world_state(self) -> WorldState:
        """Return world state with shadow-copy display positions for remote players.

        Does not mutate engine.world_state — builds a display-only view so that
        reconciliation always operates on the real predicted positions.
        With NoopShadowCopy the result is identical to engine.world_state.
        """
        if not self.shadow_copies:
            return self.engine.world_state
        display_chars = dict(self.engine.world_state.characters)
        for pid, shadow in self.shadow_copies.items():
            state = shadow.get_display_state()
            if state is not None:
                display_chars[pid] = state
        return WorldState(
            sequence_number=self.engine.world_state.sequence_number,
            characters=display_chars,
            environment=self.engine.world_state.environment,
        )

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
