from distributed_smb.domain.session import SessionInfo
from distributed_smb.domain.session_state import SessionState, SessionPhase
from distributed_smb.shared.roster import GlobalRoster, RosterEntry

def test_session_creation():
    roster = GlobalRoster()

    session = SessionInfo(
        session_id="abc",
        owner_id="p1",
        roster=roster
    )

    state = SessionState(session_info=session)

    assert state.phase == SessionPhase.WAITING

def test_full_flow():
    roster = GlobalRoster()

    p1 = RosterEntry("p1", "127.0.0.1", 5000, 0, True)
    p2 = RosterEntry("p2", "127.0.0.1", 5001, 1)

    roster.add_player(p1)
    roster.add_player(p2)

    assert roster.get_player("p2").join_index == 1