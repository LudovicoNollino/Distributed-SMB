"""Integration tests for NodeController.lobby_phase()."""

import threading
import time
from unittest.mock import patch

import pytest

from distributed_smb.application.node_controller import NodeController
from distributed_smb.network.lobby_service import launch_lobby_server, lobby_manager
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.shared.config import LOBBY_STARTUP_WAIT
from distributed_smb.shared.enums import PlayerRole

TEST_PORT = 59200


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


def _make_host() -> NodeController:
    ctrl = NodeController().bootstrap(role=PlayerRole.HOST)
    ctrl.ws_handler = WsHandler(host="127.0.0.1", port=TEST_PORT)
    return ctrl


def _make_client() -> NodeController:
    ctrl = NodeController().bootstrap(role=PlayerRole.CLIENT)
    ctrl.ws_handler = WsHandler(host="127.0.0.1", port=TEST_PORT)
    return ctrl


# ---------------------------------------------------------------------------
# Host-only: min_players=1 so no real client needed
# ---------------------------------------------------------------------------


def test_host_lobby_phase_single_player():
    host = _make_host()

    with patch("distributed_smb.application.node_controller.launch_lobby_server"):
        with patch("distributed_smb.application.node_controller.time.sleep"):
            roster = host.lobby_phase(min_players=1)

    assert host.session_id != ""
    assert len(roster.players) == 1
    assert roster.players[0].player_id == "player1"
    assert roster.players[0].is_host is True


# ---------------------------------------------------------------------------
# Full flow: host waits for client, then triggers GameStart
# ---------------------------------------------------------------------------


def test_host_and_client_lobby_phase():
    host = _make_host()
    client = _make_client()

    errors = []

    def run_host():
        try:
            with patch("distributed_smb.application.node_controller.launch_lobby_server"):
                with patch("distributed_smb.application.node_controller.time.sleep"):
                    host.lobby_phase(min_players=2)
        except Exception as exc:
            errors.append(exc)

    def run_client():
        # Wait until the host has set session_id
        deadline = time.time() + 5.0
        while not host.session_id and time.time() < deadline:
            time.sleep(0.05)
        try:
            client.lobby_phase(session_id=host.session_id)
        except Exception as exc:
            errors.append(exc)

    t_host = threading.Thread(target=run_host)
    t_client = threading.Thread(target=run_client)

    t_host.start()
    t_client.start()

    t_host.join(timeout=10.0)
    t_client.join(timeout=10.0)

    assert not errors, errors
    assert len(host.roster.players) == 2
    assert len(client.roster.players) == 2
    assert host.session_id == client.session_id
    # World contains exactly the players from the roster
    assert set(host.engine.world_state.characters) == {"player1", "player2"}
    assert set(client.engine.world_state.characters) == {"player1", "player2"}


def test_host_solo_world_has_only_one_player():
    """With min_players=1 the world must contain only the host's character."""
    host = _make_host()
    with patch("distributed_smb.application.node_controller.launch_lobby_server"):
        with patch("distributed_smb.application.node_controller.time.sleep"):
            host.lobby_phase(min_players=1)

    assert set(host.engine.world_state.characters) == {"player1"}
