from unittest.mock import patch

import pygame

from distributed_smb.application.node_controller import NodeController
from distributed_smb.main import get_controller, parse_args
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.shared.config import DEFAULT_HOST, LOBBY_WS_PORT, TICK_INTERVAL
from distributed_smb.shared.enums import NodeState, PlayerRole
from distributed_smb.shared.input import InputState


def test_bootstrap_initializes_node_controller_state():
    controller = NodeController()

    bootstrapped_controller = controller.bootstrap()

    assert bootstrapped_controller is controller
    assert controller.is_bootstrapped is True
    assert controller.lifecycle.state is NodeState.IDLE
    assert controller.tick_interval == TICK_INTERVAL


def test_build_runtime_context_exposes_expected_components():
    fake_keys = {
        pygame.K_LEFT: False,
        pygame.K_a: False,
        pygame.K_RIGHT: False,
        pygame.K_d: False,
        pygame.K_SPACE: False,
        pygame.K_UP: False,
        pygame.K_w: False,
    }
    handler = InputHandler(key_provider=lambda: fake_keys)
    controller = NodeController().bootstrap()
    controller.input_handler = handler

    runtime_context = controller.build_runtime_context()

    assert set(runtime_context) == {
        "engine",
        "input_handler",
        "local_player_id",
        "remote_player_id",
        "renderer",
        "role",
        "tick_interval",
    }
    assert runtime_context["engine"] is controller.engine
    assert runtime_context["input_handler"] is controller.input_handler
    assert runtime_context["local_player_id"] == controller.local_player_id
    assert runtime_context["remote_player_id"] == controller.remote_player_id
    assert runtime_context["renderer"] is controller.renderer
    assert runtime_context["role"] is controller.role
    assert runtime_context["tick_interval"] == controller.tick_interval
    assert isinstance(controller.input_handler.read_input(), InputState)


def test_main_returns_a_bootstrapped_controller():
    controller = get_controller()

    assert isinstance(controller, NodeController)
    assert controller.is_bootstrapped is True


def test_run_returns_false_when_presentation_runtime_is_missing():
    controller = NodeController().bootstrap()

    with patch.dict("sys.modules", {"distributed_smb.presentation.app": None}):
        started = controller.run()

    assert started is False


def test_host_bootstrap_configures_players_and_role():
    controller = NodeController().bootstrap(role=PlayerRole.HOST)

    assert controller.role is PlayerRole.HOST
    assert controller.engine.world_state.get_player(controller.local_player_id) is not None
    assert controller.engine.world_state.get_player(controller.remote_player_id) is not None


def test_host_and_client_bootstrap_use_consistent_player_spawn_positions():
    host = NodeController().bootstrap(role=PlayerRole.HOST)
    client = NodeController().bootstrap(role=PlayerRole.CLIENT)

    host_player1 = host.engine.world_state.get_player("player1")
    host_player2 = host.engine.world_state.get_player("player2")
    client_player1 = client.engine.world_state.get_player("player1")
    client_player2 = client.engine.world_state.get_player("player2")

    assert (host_player1.x, host_player1.y) == (client_player1.x, client_player1.y)
    assert (host_player2.x, host_player2.y) == (client_player2.x, client_player2.y)


def test_client_process_frame_increments_input_sequence():
    controller = NodeController().bootstrap(role=PlayerRole.CLIENT)

    class FakeUdpHandler:
        def open_socket(self):
            return None

        def send_packet_nowait(self, payload, remote_host, remote_port):
            return None

        def receive_packet_nowait(self):
            return None

    controller.udp_handler = FakeUdpHandler()

    controller.process_frame(TICK_INTERVAL, InputState(right=True))

    assert controller.input_sequence_number == 1


def test_parse_args_defaults():
    args = parse_args([])
    assert args.host_ip == DEFAULT_HOST
    assert args.session_id == ""
    assert not args.host
    assert not args.client


def test_parse_args_client_flags():
    args = parse_args(["--client", "--host-ip", "192.168.1.10", "--session-id", "abc123"])
    assert args.client is True
    assert args.host_ip == "192.168.1.10"
    assert args.session_id == "abc123"


def test_main_client_sets_ws_handler_host():
    from distributed_smb.main import main

    controller = main(role=PlayerRole.CLIENT, host_ip="192.168.1.10")
    assert controller.ws_handler.host == "192.168.1.10"
    assert controller.ws_handler.port == LOBBY_WS_PORT
    assert controller.remote_host == "192.168.1.10"
