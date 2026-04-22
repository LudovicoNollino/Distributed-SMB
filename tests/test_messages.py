import json
from dataclasses import asdict

from distributed_smb.domain.messages import RosterUpdate, SessionJoin
from distributed_smb.shared.roster import GlobalRoster, RosterEntry


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
