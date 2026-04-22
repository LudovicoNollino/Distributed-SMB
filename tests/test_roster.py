from distributed_smb.shared.roster import GlobalRoster, RosterEntry, RosterValidationError
import pytest


def test_add_player():
    roster = GlobalRoster()

    p1 = RosterEntry("p1", "127.0.0.1", 5000, 0, is_host=True)
    p2 = RosterEntry("p2", "127.0.0.1", 5001, 1, is_host=False)

    roster.add_player(p1)
    roster.add_player(p2)

    assert len(roster.players) == 2
    assert roster.get_player("p1").is_host is True


def test_join_index_order():
    roster = GlobalRoster()

    for i in range(3):
        roster.add_player(RosterEntry(f"p{i}", "127.0.0.1", 5000 + i, i))

    assert [p.join_index for p in roster.players] == [0, 1, 2]


def test_duplicate_join_index_raises():
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0))

    with pytest.raises(RosterValidationError, match="Duplicate join_index"):
        roster.add_player(RosterEntry("p2", "127.0.0.1", 5001, 0))


def test_invalid_player_id():
    with pytest.raises(RosterValidationError, match="Invalid player_id"):
        RosterEntry("", "127.0.0.1", 5000, 0)


def test_invalid_port():
    with pytest.raises(RosterValidationError, match="udp_port out of range"):
        RosterEntry("p1", "127.0.0.1", 100, 0)


def test_invalid_join_index():
    with pytest.raises(RosterValidationError, match="join_index must be >= 0"):
        RosterEntry("p1", "127.0.0.1", 5000, -1)


def test_get_host():
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0, is_host=True))
    roster.add_player(RosterEntry("p2", "127.0.0.1", 5001, 1, is_host=False))

    host = roster.get_host()
    assert host.player_id == "p1"
    assert host.is_host is True


def test_get_all_players_sorted():
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p2", "127.0.0.1", 5001, 1))
    roster.add_player(RosterEntry("p1", "127.0.0.1", 5000, 0))
    roster.add_player(RosterEntry("p3", "127.0.0.1", 5002, 2))

    sorted_players = roster.get_all_players()
    assert [p.player_id for p in sorted_players] == ["p1", "p2", "p3"]
