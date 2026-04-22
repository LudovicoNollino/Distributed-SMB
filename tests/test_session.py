from distributed_smb.domain.session import (
    GameSession,
    SessionInfo,
    HostMigrationMetadata,
    PeerRejoinMetadata,
)
from distributed_smb.domain.session_state import SessionPhase, SessionState
from distributed_smb.shared.roster import GlobalRoster, RosterEntry


def test_session_creation():
    roster = GlobalRoster()

    session = GameSession(session_id="abc", host_player_id="p1", roster=roster)

    state = SessionState(session_info=session)

    assert state.phase == SessionPhase.WAITING


def test_full_flow():
    roster = GlobalRoster()

    p1 = RosterEntry("p1", "127.0.0.1", 5000, 0, is_host=True)
    p2 = RosterEntry("p2", "127.0.0.1", 5001, 1)

    roster.add_player(p1)
    roster.add_player(p2)

    assert roster.get_player("p2").join_index == 1


def test_session_info_creation():
    """SessionInfo encapsulates shared session metadata."""
    info = SessionInfo(session_id="sess1", host_player_id="p1")

    assert info.session_id == "sess1"
    assert info.host_player_id == "p1"
    assert info.version == 1


def test_game_session_initialize_session_info():
    """Host can initialize SessionInfo."""
    session = GameSession(session_id="sess1", host_player_id="p1")
    session.initialize_session_info()

    assert session.session_info is not None
    assert session.session_info.session_id == "sess1"
    assert session.session_info.host_player_id == "p1"


def test_host_migration_metadata():
    """Migration metadata tracks host changes."""
    metadata = HostMigrationMetadata(current_host_player_id="p1")

    assert metadata.current_host_player_id == "p1"
    assert metadata.election_in_progress is False
    assert metadata.migration_version == 0


def test_game_session_initialize_migration():
    """Session can initialize migration tracking."""
    session = GameSession(session_id="sess1", host_player_id="p1")
    session.initialize_migration_metadata()

    assert session.migration_metadata is not None
    assert session.migration_metadata.current_host_player_id == "p1"


def test_peer_rejoin_metadata():
    """Rejoin metadata tracks peer connectivity."""
    metadata = PeerRejoinMetadata()

    assert len(metadata.last_heartbeat_from) == 0
    assert len(metadata.disconnected_peers) == 0


def test_game_session_initialize_rejoin():
    """Session can initialize rejoin tracking."""
    session = GameSession(session_id="sess1")
    session.initialize_rejoin_metadata()

    assert session.rejoin_metadata is not None
