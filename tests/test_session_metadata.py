import json
import tempfile
from pathlib import Path

from distributed_smb.shared.session_metadata import (
    CachedPeer,
    SessionMetadata,
    delete_session_metadata,
    read_session_metadata,
    write_session_metadata,
)


def test_write_and_read_session_metadata_round_trip(tmp_path: Path) -> None:
    metadata = SessionMetadata(
        session_id="session-123",
        local_player_id="player-1",
        peers=[
            CachedPeer(player_id="player-1", ip="192.168.0.1", join_index=0),
            CachedPeer(player_id="player-2", ip="192.168.0.2", join_index=1),
        ],
    )

    write_session_metadata(metadata, base_dir=tmp_path)
    loaded = read_session_metadata(base_dir=tmp_path)

    assert loaded == metadata
    assert (tmp_path / "session_metadata.json").exists()


def test_read_session_metadata_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_session_metadata(base_dir=tmp_path) is None


def test_read_session_metadata_corrupt_file_returns_none(tmp_path: Path) -> None:
    metadata_file = tmp_path / "session_metadata.json"
    metadata_file.write_text("{ this is not valid json", encoding="utf-8")

    assert read_session_metadata(base_dir=tmp_path) is None


def test_delete_session_metadata_is_idempotent(tmp_path: Path) -> None:
    metadata_file = tmp_path / "session_metadata.json"
    metadata_file.write_text(json.dumps({"session_id": "invalid"}), encoding="utf-8")

    delete_session_metadata(base_dir=tmp_path)
    assert not metadata_file.exists()

    # second delete should not raise
    delete_session_metadata(base_dir=tmp_path)
    assert not metadata_file.exists()
