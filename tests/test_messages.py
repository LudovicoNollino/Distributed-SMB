import json
from dataclasses import asdict

from distributed_smb.domain.messages import (
    RosterUpdate,
    SessionJoin,
    MessageValidationError,
    SessionCreate,
)
from distributed_smb.shared.roster import GlobalRoster, RosterEntry, RosterValidationError
import pytest


def test_message_creation():
    msg = SessionJoin(session_id="abc", player_id="p1", ip="127.0.0.1", port=5000)

    assert msg.player_id == "p1"
    assert msg.message_type.value == "session_join"


def test_serialization():
    msg = SessionJoin(session_id="abc", player_id="p1", ip="127.0.0.1", port=5000)

    data = json.dumps(asdict(msg))
    loaded = json.loads(data)

    assert loaded["player_id"] == "p1"


def test_roster_serialization():
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0))

    msg = RosterUpdate(roster=roster)

    data = json.dumps(asdict(msg))

    assert "p1" in data


def test_session_join_invalid_player_id():
    with pytest.raises(MessageValidationError, match="Invalid player_id"):
        SessionJoin(session_id="abc", player_id="", ip="127.0.0.1", port=5000)


def test_session_join_invalid_port():
    with pytest.raises(MessageValidationError, match="Port out of range"):
        SessionJoin(session_id="abc", player_id="p1", ip="127.0.0.1", port=100)


def test_session_join_invalid_session_id():
    with pytest.raises(MessageValidationError, match="Invalid session_id"):
        SessionJoin(session_id="", player_id="p1", ip="127.0.0.1", port=5000)


def test_session_create_invalid_player_id():
    with pytest.raises(MessageValidationError, match="Invalid player_id"):
        SessionCreate(player_id="")


def test_roster_update_duplicate_join_index():
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0))

    with pytest.raises(RosterValidationError, match="Duplicate join_index"):
        roster.add_player(RosterEntry("p2", "127.0.0.1", 5001, 0))


def test_roster_update_validates_on_message():
    """RosterUpdate message validates roster state."""
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0))
    roster.add_player(RosterEntry("p2", "127.0.0.1", 5001, 1))

    # Should not raise - valid roster
    msg = RosterUpdate(roster=roster)
    assert len(msg.roster.players) == 2
