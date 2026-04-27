"""End-to-end localhost integration test: lobby coordination + UDP gameplay."""

import threading
import time
from unittest.mock import patch

import pytest

from distributed_smb.application.node_controller import NodeController
from distributed_smb.network.lobby_service import launch_lobby_server, lobby_manager
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.shared.config import LOBBY_STARTUP_WAIT
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState

TEST_WS_PORT = 59300
FRAME_DT = 1 / 60


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def start_server():
    lobby_manager.reset()
    launch_lobby_server(host="127.0.0.1", port=TEST_WS_PORT)
    time.sleep(LOBBY_STARTUP_WAIT)


@pytest.fixture(autouse=True)
def reset_lobby():
    lobby_manager.reset()
    yield
    lobby_manager.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_lobby(host: NodeController, client: NodeController) -> list:
    errors = []

    def run_host():
        try:
            with patch("distributed_smb.application.node_controller.launch_lobby_server"):
                with patch("distributed_smb.application.node_controller.time.sleep"):
                    host.lobby_phase(min_players=2)
        except Exception as exc:
            errors.append(exc)

    def run_client():
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

    return errors


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_lobby_produces_consistent_session():
    """Both nodes finish lobby with the same session_id and a 2-player roster."""
    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    client.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    errors = _run_lobby(host, client)

    assert not errors, errors
    assert host.session_id == client.session_id
    assert host.session_id != ""
    assert len(host.roster.players) == 2
    assert len(client.roster.players) == 2


def test_world_contains_only_roster_players_after_lobby():
    """After lobby_phase the world has exactly the two roster players — no extras."""
    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    client.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    _run_lobby(host, client)

    assert set(host.engine.world_state.characters) == {"player1", "player2"}
    assert set(client.engine.world_state.characters) == {"player1", "player2"}


def test_udp_gameplay_frames_are_exchanged():
    """After lobby, host and client exchange real UDP packets over localhost."""
    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    client.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    errors = _run_lobby(host, client)
    assert not errors, errors

    # Drive several interleaved frames:
    #   client sends PlayerInputPacket → host receives it
    #   host sends WorldStateSnapshot → client receives it
    ROUNDS = 10
    for _ in range(ROUNDS):
        client.process_frame(FRAME_DT, InputState(right=True))
        time.sleep(0.02)
        host.process_frame(FRAME_DT, InputState())
        time.sleep(0.02)

    host.udp_handler.close_socket()
    client.udp_handler.close_socket()

    assert host.received_input_packets > 0, (
        "Host received no PlayerInputPacket from client over UDP"
    )
    assert client.received_snapshots > 0, (
        "Client received no WorldStateSnapshot from host over UDP"
    )


def test_host_applies_client_input_to_world():
    """The host's authoritative world state moves player2 when client sends right input."""
    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    client = NodeController().bootstrap(role=PlayerRole.CLIENT)
    client.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)

    errors = _run_lobby(host, client)
    assert not errors, errors

    initial_x = host.engine.world_state.characters["player2"].x

    for _ in range(20):
        client.process_frame(FRAME_DT, InputState(right=True))
        time.sleep(0.02)
        host.process_frame(FRAME_DT, InputState())
        time.sleep(0.02)

    host.udp_handler.close_socket()
    client.udp_handler.close_socket()

    final_x = host.engine.world_state.characters["player2"].x
    assert final_x > initial_x, (
        f"player2 did not move right on host: initial_x={initial_x}, final_x={final_x}"
    )
