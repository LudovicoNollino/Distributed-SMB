from __future__ import annotations

import logging
import math
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Deque

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.world import WorldState
from distributed_smb.shared.config import DIVERGENCE_THRESHOLD, TICK_INTERVAL
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.sync import WorldStateSnapshot

LOGGER = logging.getLogger(__name__)

# Reconciliation jumps below this (px) are imperceptible and not logged.
RECONCILE_LOG_THRESHOLD = 1.0


@dataclass(slots=True)
class InputHistoryEntry:
    sequence_number: int
    input_state: InputState
    predicted_state_snapshot: WorldState
    dt: float = TICK_INTERVAL


class InputHistoryBuffer:
    def __init__(self, capacity: int = 64) -> None:
        self.capacity = capacity
        self._entries: Deque[InputHistoryEntry] = deque(maxlen=capacity)

    def push(
        self,
        sequence_number: int,
        input_state: InputState,
        predicted_state_snapshot: WorldState,
        dt: float = TICK_INTERVAL,
    ) -> None:
        snapshot = deepcopy(predicted_state_snapshot)
        self._entries.append(
            InputHistoryEntry(
                sequence_number=sequence_number,
                input_state=input_state,
                predicted_state_snapshot=snapshot,
                dt=dt,
            )
        )

    def acknowledge(self, sequence_number: int) -> None:
        while self._entries and self._entries[0].sequence_number <= sequence_number:
            self._entries.popleft()

    def get_unacknowledged(self) -> list[InputHistoryEntry]:
        return list(self._entries)

    def find(self, sequence_number: int) -> InputHistoryEntry | None:
        for entry in self._entries:
            if entry.sequence_number == sequence_number:
                return entry
        return None


class PredictionEngine:
    def __init__(
        self, engine: GameEngine, local_player_id: str, history_capacity: int = 64
    ) -> None:
        self.engine = engine
        self.local_player_id = local_player_id
        self.buffer = InputHistoryBuffer(capacity=history_capacity)

    def predict(self, input_state: InputState, dt: float = TICK_INTERVAL) -> None:
        next_seq = self.engine.world_state.sequence_number + 1
        self.buffer.push(next_seq, input_state, self.engine.world_state, dt)

    def reconcile(self, authoritative_snapshot: WorldStateSnapshot) -> None:
        world_state = authoritative_snapshot.world_state
        client_seq_before = self.engine.world_state.sequence_number
        predicted_player = self.engine.world_state.get_player(self.local_player_id)
        predicted_pos = (
            (predicted_player.x, predicted_player.y) if predicted_player else None
        )

        self.buffer.acknowledge(world_state.sequence_number)
        pending_inputs = self.buffer.get_unacknowledged()
        # Preserve local environment: blocks/power-ups/gates are managed exclusively
        # by WS events — the UDP snapshot must not override them.
        local_env = self.engine.world_state.environment
        self.engine.world_state = deepcopy(world_state)
        self.engine.world_state.environment = local_env
        if pending_inputs:
            self._replay_pending(pending_inputs)

        self._log_correction(
            client_seq_before, world_state.sequence_number, pending_inputs, predicted_pos
        )

    def _log_correction(
        self,
        client_seq_before: int,
        host_seq: int,
        pending_inputs: list[InputHistoryEntry],
        predicted_pos: tuple[float, float] | None,
    ) -> None:
        if predicted_pos is None:
            return
        reconciled_player = self.engine.world_state.get_player(self.local_player_id)
        if reconciled_player is None:
            return
        delta_x = reconciled_player.x - predicted_pos[0]
        delta_y = reconciled_player.y - predicted_pos[1]
        distance = math.hypot(delta_x, delta_y)
        if distance < RECONCILE_LOG_THRESHOLD:
            return
        LOGGER.info(
            "reconcile correction: %.1fpx (dx=%.1f dy=%.1f) "
            "client_seq=%d host_seq=%d pending_replayed=%d",
            distance,
            delta_x,
            delta_y,
            client_seq_before,
            host_seq,
            len(pending_inputs),
        )

    def should_rollback(self, predicted: WorldState, authoritative: WorldState) -> bool:
        predicted_player = predicted.get_player(self.local_player_id)
        authoritative_player = authoritative.get_player(self.local_player_id)

        if predicted_player is None or authoritative_player is None:
            return False

        delta_x = predicted_player.x - authoritative_player.x
        delta_y = predicted_player.y - authoritative_player.y
        distance = math.hypot(delta_x, delta_y)

        return distance > DIVERGENCE_THRESHOLD

    def pending_count(self) -> int:
        return len(self.buffer.get_unacknowledged())

    def _replay_pending(self, pending_inputs: list[InputHistoryEntry]) -> None:
        for entry in pending_inputs:
            self.engine.tick(entry.dt, {self.local_player_id: entry.input_state})
            entry.predicted_state_snapshot = deepcopy(self.engine.world_state)
