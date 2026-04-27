import json

import pytest
from fastapi.testclient import TestClient

from distributed_smb.domain.messages import MessageType
from distributed_smb.network.lobby_service import app, lobby_manager
from distributed_smb.network.serializer import Serializer

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
        assert players[0]["player_id"] == "host1"
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
