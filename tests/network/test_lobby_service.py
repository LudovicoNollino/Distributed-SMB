import json

import pytest
from fastapi.testclient import TestClient

from distributed_smb.network.lobby_service import app, lobby_manager
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.enums import MessageType

client = TestClient(app)
s = Serializer()


@pytest.fixture(autouse=True)
def reset_lobby():
    lobby_manager.reset()
    yield
    lobby_manager.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_msg(player_id="host1", ip="127.0.0.1", udp_port=50010):
    return json.dumps(
        {"message_type": "session_create", "player_id": player_id, "ip": ip, "udp_port": udp_port}
    )


def _join_msg(session_id, player_id="client1", ip="127.0.0.1", port=50011):
    return json.dumps(
        {
            "message_type": "session_join",
            "session_id": session_id,
            "player_id": player_id,
            "ip": ip,
            "port": port,
        }
    )


def _game_start_msg(session_id):
    return json.dumps({"message_type": "game_start", "session_id": session_id})


# ---------------------------------------------------------------------------
# session_create
# ---------------------------------------------------------------------------


def test_session_create_returns_session_created():
    with client.websocket_connect("/lobby") as ws:
        ws.send_text(_create_msg())

        created = json.loads(ws.receive_text())
        assert created["message_type"] == MessageType.SESSION_CREATED
        assert "session_id" in created
        assert created["join_index"] == 0

        # lobby also broadcasts roster_update to the host
        roster_msg = json.loads(ws.receive_text())
        assert roster_msg["message_type"] == MessageType.ROSTER_UPDATE
        players = roster_msg["roster"]["players"]
        assert len(players) == 1
        assert players[0]["player_id"] == "player1"
        assert players[0]["is_host"] is True


# ---------------------------------------------------------------------------
# session_join
# ---------------------------------------------------------------------------


def test_session_join_assigns_incremental_join_index():
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        created = json.loads(host_ws.receive_text())
        session_id = created["session_id"]
        host_ws.receive_text()  # discard first roster_update

        with client.websocket_connect("/lobby") as client_ws:
            client_ws.send_text(_join_msg(session_id))

            joined = json.loads(client_ws.receive_text())
            assert joined["message_type"] == MessageType.SESSION_JOINED
            assert joined["join_index"] == 1

            # both connections receive roster_update
            roster_for_client = json.loads(client_ws.receive_text())
            roster_for_host = json.loads(host_ws.receive_text())

            assert roster_for_client["message_type"] == MessageType.ROSTER_UPDATE
            assert roster_for_host["message_type"] == MessageType.ROSTER_UPDATE

            players_c = roster_for_client["roster"]["players"]
            players_h = roster_for_host["roster"]["players"]
            assert len(players_c) == 2
            assert len(players_h) == 2


def test_second_join_gets_join_index_2():
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        created = json.loads(host_ws.receive_text())
        session_id = created["session_id"]
        host_ws.receive_text()  # discard roster

        with client.websocket_connect("/lobby") as c1_ws:
            c1_ws.send_text(_join_msg(session_id, player_id="c1", port=50011))
            joined1 = json.loads(c1_ws.receive_text())
            assert joined1["join_index"] == 1
            # consume roster broadcasts
            c1_ws.receive_text()
            host_ws.receive_text()

            with client.websocket_connect("/lobby") as c2_ws:
                c2_ws.send_text(_join_msg(session_id, player_id="c2", port=50012))
                joined2 = json.loads(c2_ws.receive_text())
                assert joined2["join_index"] == 2


# ---------------------------------------------------------------------------
# game_start
# ---------------------------------------------------------------------------


def test_game_start_broadcast_to_all():
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        created = json.loads(host_ws.receive_text())
        session_id = created["session_id"]
        host_ws.receive_text()  # discard roster

        with client.websocket_connect("/lobby") as client_ws:
            client_ws.send_text(_join_msg(session_id))
            client_ws.receive_text()  # joined
            client_ws.receive_text()  # roster
            host_ws.receive_text()  # roster

            host_ws.send_text(_game_start_msg(session_id))

            start_for_host = json.loads(host_ws.receive_text())
            start_for_client = json.loads(client_ws.receive_text())

            assert start_for_host["message_type"] == MessageType.GAME_START
            assert start_for_client["message_type"] == MessageType.GAME_START
            assert start_for_host["session_id"] == session_id


def test_game_start_marks_session_active():
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        created = json.loads(host_ws.receive_text())
        session_id = created["session_id"]
        host_ws.receive_text()  # discard roster

        assert not lobby_manager.is_active(session_id)
        host_ws.send_text(_game_start_msg(session_id))
        host_ws.receive_text()  # consume broadcast
        assert lobby_manager.is_active(session_id)


# ---------------------------------------------------------------------------
# register_active_session (M9 rejoin)
# ---------------------------------------------------------------------------


def test_register_active_session_creates_active_session():
    from distributed_smb.shared.roster import GlobalRoster, RosterEntry

    roster = GlobalRoster()
    roster.add_player(
        RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50010, join_index=1)
    )
    lobby_manager.register_active_session("abc123", roster, next_join_index=2)

    assert lobby_manager.is_active("abc123")


def test_session_join_for_active_session_sends_game_start_immediately():
    """Rejoining node must receive GameStart right after SessionJoined (M9 fix #3)."""
    from distributed_smb.shared.roster import GlobalRoster, RosterEntry

    roster = GlobalRoster()
    roster.add_player(
        RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50010, join_index=1)
    )
    lobby_manager.register_active_session("abc123", roster, next_join_index=2)

    with client.websocket_connect("/lobby") as rejoining_ws:
        rejoining_ws.send_text(
            json.dumps(
                {
                    "message_type": "session_join",
                    "session_id": "abc123",
                    "player_id": "player3",
                    "ip": "10.0.0.3",
                    "port": 49500,
                }
            )
        )

        # 1) SessionJoined with new join_index
        joined = json.loads(rejoining_ws.receive_text())
        assert joined["message_type"] == MessageType.SESSION_JOINED
        assert joined["join_index"] == 2

        # 2) RosterUpdate broadcast
        roster_msg = json.loads(rejoining_ws.receive_text())
        assert roster_msg["message_type"] == MessageType.ROSTER_UPDATE

        # 3) GameStart sent immediately because session is active
        game_start = json.loads(rejoining_ws.receive_text())
        assert game_start["message_type"] == MessageType.GAME_START
        assert game_start["session_id"] == "abc123"


def test_session_recreate_registers_session_and_sends_created_ack():
    """SESSION_RECREATE creates an active session with the preserved session_id (M9)."""
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(
            json.dumps(
                {
                    "message_type": "session_recreate",
                    "session_id": "restored-session-abc",
                    "next_join_index": 2,
                    "host_ip": "192.168.1.10",
                    "host_udp_port": 50010,
                    "host_join_index": 1,
                }
            )
        )

        ack = json.loads(host_ws.receive_text())
        assert ack["message_type"] == MessageType.SESSION_CREATED
        assert ack["session_id"] == "restored-session-abc"
        assert lobby_manager.is_active("restored-session-abc")
        roster = lobby_manager.get_roster("restored-session-abc")
        host_entry = next((e for e in roster.get_all_players() if e.is_host), None)
        assert host_entry is not None
        assert host_entry.host == "192.168.1.10"
        assert host_entry.join_index == 1


def _leave_msg(session_id, join_index):
    return json.dumps(
        {
            "message_type": "session_leave",
            "session_id": session_id,
            "join_index": join_index,
        }
    )


def test_client_leaving_the_lobby_is_removed_from_the_roster():
    """A client that announces its departure must disappear from the roster of
    everyone still in the lobby."""
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        session_id = json.loads(host_ws.receive_text())["session_id"]
        host_ws.receive_text()  # first roster_update

        with client.websocket_connect("/lobby") as client_ws:
            client_ws.send_text(_join_msg(session_id))
            joined = json.loads(client_ws.receive_text())
            client_ws.receive_text()  # roster_update
            assert len(json.loads(host_ws.receive_text())["roster"]["players"]) == 2

            client_ws.send_text(_leave_msg(session_id, joined["join_index"]))
            roster = json.loads(host_ws.receive_text())
            client_ws.receive_text()  # the leaver gets the broadcast too

    assert roster["message_type"] == MessageType.ROSTER_UPDATE
    assert [p["player_id"] for p in roster["roster"]["players"]] == ["player1"]


def test_host_leaving_the_lobby_closes_the_room():
    """The room has no meaning without its host: the others get SessionClosed
    (they return to the menu) and the session is dropped entirely."""
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        session_id = json.loads(host_ws.receive_text())["session_id"]
        host_ws.receive_text()

        with client.websocket_connect("/lobby") as client_ws:
            client_ws.send_text(_join_msg(session_id))
            client_ws.receive_text()  # session_joined
            client_ws.receive_text()  # roster_update
            host_ws.receive_text()  # roster_update

            host_ws.send_text(_leave_msg(session_id, 0))
            closed = json.loads(client_ws.receive_text())
            host_ws.receive_text()  # the host gets its own broadcast too

    assert closed["message_type"] == MessageType.SESSION_CLOSED
    assert closed["session_id"] == session_id
    assert not lobby_manager.is_active(session_id)


def test_leaving_works_after_the_game_has_started():
    """The post-victory lobby runs on a session already marked active — an
    explicit leave must still update the roster there."""
    from distributed_smb.shared.roster import GlobalRoster, RosterEntry

    roster = GlobalRoster()
    roster.add_player(
        RosterEntry(player_id="player2", host="10.0.0.2", udp_port=50010, join_index=1)
    )
    lobby_manager.register_active_session("active-1", roster, next_join_index=2)

    with client.websocket_connect("/lobby") as ws:
        ws.send_text(_join_msg("active-1", player_id="player3", port=49500))
        joined = json.loads(ws.receive_text())
        ws.receive_text()  # roster_update
        ws.receive_text()  # game_start

        ws.send_text(_leave_msg("active-1", joined["join_index"]))
        roster_msg = json.loads(ws.receive_text())

    assert [p["player_id"] for p in roster_msg["roster"]["players"]] == ["player2"]


def test_a_dropped_connection_does_not_evict_anyone():
    """A socket dying is not a departure: it also happens on a crash or during
    a host migration, where membership belongs to the host."""
    with client.websocket_connect("/lobby") as host_ws:
        host_ws.send_text(_create_msg())
        session_id = json.loads(host_ws.receive_text())["session_id"]
        host_ws.receive_text()

        with client.websocket_connect("/lobby") as client_ws:
            client_ws.send_text(_join_msg(session_id))
            client_ws.receive_text()
            client_ws.receive_text()
            host_ws.receive_text()

    players = {e.player_id for e in lobby_manager.get_roster(session_id).get_all_players()}
    assert players == {"player1", "player2"}
