from __future__ import annotations

import math
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Deque

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.world import WorldState
from distributed_smb.shared.config import DIVERGENCE_THRESHOLD
from distributed_smb.shared.input import InputState


@dataclass(slots=True)
class InputHistoryEntry:
    sequence_number: int
    input_state: InputState
    predicted_state_snapshot: WorldState


class InputHistoryBuffer:
    def __init__(self, capacity: int = 64) -> None:
        self.capacity = capacity
        self._entries: Deque[InputHistoryEntry] = deque(maxlen=capacity)

    def push(
        self, sequence_number: int, input_state: InputState, predicted_state_snapshot: WorldState
    ) -> None:
        snapshot = deepcopy(predicted_state_snapshot)
        self._entries.append(
            InputHistoryEntry(
                sequence_number=sequence_number,
                input_state=input_state,
                predicted_state_snapshot=snapshot,
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

    def predict(self, sequence_number: int, input_state: InputState, dt: float) -> WorldState:
        self.engine.tick(dt, {self.local_player_id: input_state})
        self.buffer.push(sequence_number, input_state, self.engine.world_state)
        return deepcopy(self.engine.world_state)

    def reconcile(self, authoritative_snapshot: WorldState, dt: float) -> bool:
        matching_entry = self.buffer.find(authoritative_snapshot.sequence_number)
        self.buffer.acknowledge(authoritative_snapshot.sequence_number)

        if matching_entry is None:
            pending_inputs = self.buffer.get_unacknowledged()
            self.engine.world_state = deepcopy(authoritative_snapshot)
            if pending_inputs:
                self._replay_pending(pending_inputs, dt)
                return True
            return False

        if self.should_rollback(matching_entry.predicted_state_snapshot, authoritative_snapshot):
            self.engine.world_state = deepcopy(authoritative_snapshot)
            pending_inputs = self.buffer.get_unacknowledged()
            self._replay_pending(pending_inputs, dt)
            return True

        return False

    def should_rollback(self, predicted: WorldState, authoritative: WorldState) -> bool:
        predicted_player = predicted.get_player(self.local_player_id)
        authoritative_player = authoritative.get_player(self.local_player_id)

        if predicted_player is None or authoritative_player is None:
            return False

        delta_x = predicted_player.x - authoritative_player.x
        delta_y = predicted_player.y - authoritative_player.y
        distance = math.hypot(delta_x, delta_y)

        return distance > DIVERGENCE_THRESHOLD

    def _replay_pending(self, pending_inputs: list[InputHistoryEntry], dt: float) -> None:
        for entry in pending_inputs:
            self.engine.tick(dt, {self.local_player_id: entry.input_state})
            entry.predicted_state_snapshot = deepcopy(self.engine.world_state)
