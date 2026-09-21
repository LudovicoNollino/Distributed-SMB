"""End-to-end localhost integration test: lobby coordination + UDP gameplay."""

import time

import pytest

from distributed_smb.application.node_controller import NodeController
from distributed_smb.application.protocols import NoopGameEventBroker, NoopLobbyService
from distributed_smb.network.lobby.service import launch_lobby_server, lobby_manager
from distributed_smb.network.transport.websocket import WsHandler
from distributed_smb.shared.config import LOBBY_STARTUP_WAIT
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState

TEST_WS_PORT = 59300
FRAME_DT = 1 / 60


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


def _make_node(role: PlayerRole) -> NodeController:
    node = NodeController(
        game_event_broker=NoopGameEventBroker(),
        lobby_service=NoopLobbyService(),
    ).bootstrap(role=role)
    node.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)
    return node


def test_client_input_moves_its_player_on_the_host_over_udp(run_lobby_pair):
    """After the lobby, client input reaches the host over real UDP and the
    host's snapshots reach the client back."""
    host = _make_node(PlayerRole.HOST)
    client = _make_node(PlayerRole.CLIENT)

    errors = run_lobby_pair(host, client)
    assert not errors, errors

    initial_x = host.engine.world_state.characters["player2"].x

    for _ in range(20):
        client.process_frame(FRAME_DT, InputState(right=True))
        time.sleep(0.02)
        host.process_frame(FRAME_DT, InputState())
        time.sleep(0.02)

    host.udp_handler.close_socket()
    client.udp_handler.close_socket()

    assert host.received_input_packets > 0
    assert client.received_snapshots > 0
    assert host.engine.world_state.characters["player2"].x > initial_x
