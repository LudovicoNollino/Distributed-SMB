"""Unit tests for EnvironmentalStateBuffer."""

from unittest.mock import MagicMock

from distributed_smb.application.election import EnvironmentalStateBuffer
from distributed_smb.shared.messages.sync import WorldStateSnapshot


def _make_snapshot(seq: int) -> WorldStateSnapshot:
    world_state = MagicMock()
    world_state.sequence_number = seq
    snap = WorldStateSnapshot.__new__(WorldStateSnapshot)
    object.__setattr__(snap, "sequence_number", seq)
    object.__setattr__(snap, "world_state", world_state)
    return snap


class TestEnvironmentalStateBuffer:
    def test_get_last_returns_none_before_any_update(self):
        buf = EnvironmentalStateBuffer()
        assert buf.get_last() is None

    def test_update_stores_snapshot(self):
        buf = EnvironmentalStateBuffer()
        snap = _make_snapshot(1)
        buf.update(snap)
        assert buf.get_last() is snap

    def test_update_replaces_previous_snapshot(self):
        buf = EnvironmentalStateBuffer()
        snap1 = _make_snapshot(1)
        snap2 = _make_snapshot(2)
        buf.update(snap1)
        buf.update(snap2)
        assert buf.get_last() is snap2

    def test_multiple_updates_keep_only_last(self):
        buf = EnvironmentalStateBuffer()
        for seq in range(10):
            buf.update(_make_snapshot(seq))
        assert buf.get_last().sequence_number == 9
