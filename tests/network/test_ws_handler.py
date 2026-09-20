import time

import pytest

from distributed_smb.network.lobby_service import launch_lobby_server, lobby_manager
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.shared.config import LOBBY_STARTUP_WAIT
from distributed_smb.shared.messages.session import (
    RosterUpdate,
    SessionCreate,
    SessionCreated,
)

TEST_PORT = 60000


def _poll_until(handler: WsHandler, timeout: float = 2.0):
    """Poll inbox until a message arrives or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = handler.poll()
        if msg is not None:
            return msg
        time.sleep(0.02)
    return None


@pytest.fixture(scope="module", autouse=True)
def start_server():
    lobby_manager.reset()
    launch_lobby_server(host="127.0.0.1", port=TEST_PORT)
    time.sleep(LOBBY_STARTUP_WAIT)


@pytest.fixture(autouse=True)
def reset_lobby():
    lobby_manager.reset()
    yield
    lobby_manager.reset()


def test_connect_and_session_create():
    handler = WsHandler(host="127.0.0.1", port=TEST_PORT)
    handler.connect()

    handler.send(SessionCreate(player_id="host1", ip="127.0.0.1", udp_port=50010))

    created = _poll_until(handler)
    assert isinstance(created, SessionCreated)
    assert created.join_index == 0
    assert created.session_id != ""

    roster_msg = _poll_until(handler)
    assert isinstance(roster_msg, RosterUpdate)
    assert len(roster_msg.roster.players) == 1
    assert roster_msg.roster.players[0].player_id == "player1"

    handler.close()
