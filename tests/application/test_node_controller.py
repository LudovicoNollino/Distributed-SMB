from unittest.mock import patch

import pygame

from distributed_smb.application.node_controller import NodeController
from distributed_smb.main import get_controller
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.shared.config import TICK_INTERVAL
from distributed_smb.shared.enums import NodeState
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

    assert set(runtime_context) == {"engine", "input_handler", "renderer", "tick_interval"}
    assert runtime_context["engine"] is controller.engine
    assert runtime_context["input_handler"] is controller.input_handler
    assert runtime_context["renderer"] is controller.renderer
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
