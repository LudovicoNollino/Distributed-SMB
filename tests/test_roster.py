from distributed_smb.shared.roster import GlobalRoster, RosterEntry


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
