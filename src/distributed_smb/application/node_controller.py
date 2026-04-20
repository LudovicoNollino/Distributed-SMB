"""Orchestrates presentation, domain, and network components."""

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.lifecycle import NodeLifecycle
from distributed_smb.network.lobby_service import LobbyService
from distributed_smb.network.serializer import Serializer
from distributed_smb.network.udp_handler import UdpHandler
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.presentation.renderer import Renderer
from distributed_smb.shared.config import (
    DEFAULT_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_UDP_PORT,
    TICK_INTERVAL,
)
from distributed_smb.shared.roster import GlobalRoster

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class NodeController:
    """Coordinates the node runtime without embedding domain logic."""

    lifecycle: NodeLifecycle = field(default_factory=NodeLifecycle)
    roster: GlobalRoster = field(default_factory=GlobalRoster)
    engine: GameEngine = field(default_factory=GameEngine)
    renderer: Renderer = field(default_factory=Renderer)
    input_handler: InputHandler = field(default_factory=InputHandler)
    udp_handler: UdpHandler = field(
        default_factory=lambda: UdpHandler(host=DEFAULT_HOST, port=DEFAULT_UDP_PORT)
    )
    ws_handler: WsHandler = field(
        default_factory=lambda: WsHandler(host=DEFAULT_HOST, port=DEFAULT_TCP_PORT)
    )
    lobby_service: LobbyService = field(default_factory=LobbyService)
    serializer: Serializer = field(default_factory=Serializer)
    tick_interval: float = TICK_INTERVAL
    is_bootstrapped: bool = False

    def bootstrap(self) -> "NodeController":
        """Prepare the application components for the future runtime loop."""
        LOGGER.info("Bootstrapping node controller")
        self.lifecycle.move_to_idle()
        self.is_bootstrapped = True
        LOGGER.info(
            "Bootstrap completed: state=%s, tick_interval=%.4f, renderer=%sx%s",
            self.lifecycle.state,
            self.tick_interval,
            self.renderer.width,
            self.renderer.height,
        )
        return self

    def build_runtime_context(self) -> dict[str, object]:
        """Expose the components wired by the controller.

        This keeps the bootstrap contract explicit while the concrete game loop
        is still being implemented in the next integration step.
        """
        context = {
            "engine": self.engine,
            "renderer": self.renderer,
            "input_handler": self.input_handler,
            "tick_interval": self.tick_interval,
        }
        LOGGER.info("Runtime context ready: %s", ", ".join(sorted(context)))
        return context

    def _load_game_app_class(self) -> type[Any] | None:
        """Load the optional Pygame runtime provided by the presentation layer."""
        try:
            module = importlib.import_module("distributed_smb.presentation.app")
        except ModuleNotFoundError:
            LOGGER.info("Presentation runtime not available yet: expected presentation.app.GameApp")
            return None

        game_app_class = getattr(module, "GameApp", None)
        if game_app_class is None:
            LOGGER.warning("presentation.app found, but GameApp is missing")
            return None
        return game_app_class

    def run(self) -> bool:
        """Run the application if the presentation runtime is available."""
        if not self.is_bootstrapped:
            self.bootstrap()

        game_app_class = self._load_game_app_class()
        if game_app_class is None:
            LOGGER.info(
                "Application bootstrap completed, waiting for presentation runtime integration"
            )
            return False

        LOGGER.info("Delegating execution to presentation runtime")
        app = game_app_class(
            engine=self.engine,
            input_handler=self.input_handler,
            renderer=self.renderer,
        )
        app.run()
        return True
