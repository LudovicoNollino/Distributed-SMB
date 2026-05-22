"""Host-side frame synchronisation mixin."""

import logging
import time

from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.sync import WorldStateSnapshot

LOGGER = logging.getLogger(__name__)


class HostGameplayMixin:
    def _drain_remote_input_packets(self) -> None:
        """Poll incoming client input packets and cache the latest valid ones."""
        while True:
            packet = self.udp_handler.receive_packet_nowait()
            if packet is None:
                return
            payload, _address = packet
            decoded = self.serializer.decode_message(payload)
            if not isinstance(decoded, PlayerInputPacket):
                continue

            last_sequence = self.last_remote_input_sequence.get(decoded.player_id, -1)
            if decoded.sequence_number <= last_sequence:
                continue

            self.last_remote_input_sequence[decoded.player_id] = decoded.sequence_number
            self.cached_remote_inputs[decoded.player_id] = decoded.input_state
            self.last_input_time[decoded.player_id] = time.time()
            self.received_input_packets += 1

    def _build_host_inputs(self, local_input: InputState) -> dict[str, InputState]:
        """Combine local and remote input streams into one authoritative map."""
        return {
            self.local_player_id: local_input,
            self.remote_player_id: self.cached_remote_inputs.get(
                self.remote_player_id,
                InputState(),
            ),
        }

    def _send_world_state_snapshot(self) -> None:
        """Broadcast the authoritative world state to the remote client."""
        snapshot = WorldStateSnapshot(
            sequence_number=self.engine.world_state.sequence_number,
            world_state=self.engine.world_state,
        )
        payload = self.serializer.encode_message(snapshot)
        self.udp_handler.send_packet_nowait(payload, self.remote_host, self.remote_port)
        self.sent_snapshots += 1

    def _process_host_frame(self, dt: float, local_input: InputState) -> object:
        """Run one authoritative host frame: drain inputs, tick, broadcast snapshot."""
        self._check_player_disconnections()
        self._drain_remote_input_packets()
        authoritative_inputs = self._build_host_inputs(local_input)
        self.engine.tick(dt, authoritative_inputs)
        for event in self.engine.events:
            self._send_game_event(event)
        self.engine.events.clear()
        self._send_world_state_snapshot()
        return self.engine.world_state
