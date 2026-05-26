"""Thin orchestrator: wires domain, network, and presentation components."""

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

from distributed_smb.application.client_gameplay import ClientGameplayMixin
from distributed_smb.application.game_event_dispatcher import GameEventMixin
from distributed_smb.application.host_gameplay import HostGameplayMixin
from distributed_smb.application.lobby_coordinator import (
    LobbyCancelledError,
    LobbyMixin,
    LobbyUpdateCallback,
    StartRequestedCallback,
)
from distributed_smb.application.protocols import (
    GameEventBrokerProtocol,
    LobbyServiceProtocol,
)
from distributed_smb.application.reconciliation import (
    NoopPredictionEngine,
    NoopShadowCopy,
    PredictionEngine,
    PredictionEngineProtocol,
    ShadowCopyProtocol,
)
from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.lifecycle import NodeLifecycle
from distributed_smb.network.game_event_server import GameEventBroker
from distributed_smb.network.lobby_service import LobbyService
from distributed_smb.network.serializer import Serializer
from distributed_smb.network.udp_handler import UdpHandler
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.presentation.input_handler import ControlScheme, InputHandler
from distributed_smb.presentation.renderer import Renderer
from distributed_smb.shared.config import (
    CLIENT_PLAYER_ID,
    CLIENT_UDP_PORT,
    DEFAULT_HOST,
    DEFAULT_PACKET_DROP_RATE,
    DEFAULT_UDP_PORT,
    GAME_EVENT_WS_PATH,
    GAME_EVENT_WS_PORT,
    HOST_PLAYER_ID,
    HOST_UDP_PORT,
    INPUT_HISTORY_SIZE,
    LOBBY_WS_PORT,
    TICK_INTERVAL,
)
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState
from distributed_smb.shared.roster import GlobalRoster

LOGGER = logging.getLogger(__name__)

__all__ = [
    "NodeController",
    "LobbyCancelledError",
    "LobbyUpdateCallback",
    "StartRequestedCallback",
]


@dataclass(slots=True)
class NodeController(LobbyMixin, HostGameplayMixin, ClientGameplayMixin, GameEventMixin):
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
        default_factory=lambda: WsHandler(host=DEFAULT_HOST, port=LOBBY_WS_PORT)
    )
    game_event_handler: WsHandler = field(
        default_factory=lambda: WsHandler(
            host=DEFAULT_HOST, port=GAME_EVENT_WS_PORT, path=GAME_EVENT_WS_PATH
        )
    )
    session_id: str = ""
    local_ip: str = DEFAULT_HOST
    serializer: Serializer = field(default_factory=Serializer)
    tick_interval: float = TICK_INTERVAL
    is_bootstrapped: bool = False
    role: PlayerRole = PlayerRole.HOST
    local_player_id: str = HOST_PLAYER_ID
    remote_player_id: str = CLIENT_PLAYER_ID
    remote_host: str = DEFAULT_HOST
    remote_port: int = CLIENT_UDP_PORT
    input_sequence_number: int = 0
    last_remote_input_sequence: dict[str, int] = field(default_factory=dict)
    last_snapshot_sequence: int = 0
    cached_remote_inputs: dict[str, InputState] = field(default_factory=dict)
    sent_input_packets: int = 0
    received_input_packets: int = 0
    sent_snapshots: int = 0
    received_snapshots: int = 0
    last_input_time: dict[str, float] = field(default_factory=dict)
    prediction_engine: PredictionEngineProtocol = field(default_factory=NoopPredictionEngine)
    shadow_copies: dict[str, ShadowCopyProtocol] = field(default_factory=dict)
    shadow_copy_factory: type = field(default=NoopShadowCopy)
    game_event_broker: GameEventBrokerProtocol = field(default_factory=GameEventBroker)
    lobby_service: LobbyServiceProtocol = field(default_factory=LobbyService)

    def __post_init__(self) -> None:
        if isinstance(self.prediction_engine, NoopPredictionEngine):
            self.prediction_engine._engine = self.engine

    def _init_shadow_copies(self) -> None:
        """Initialise one ShadowCopy per remote player (CLIENT only, called after lobby)."""
        if self.role is not PlayerRole.CLIENT:
            return
        self.shadow_copies = {
            pid: self.shadow_copy_factory()
            for pid in self.engine.world_state.characters
            if pid != self.local_player_id
        }

    def bootstrap(
        self,
        *,
        role: PlayerRole = PlayerRole.HOST,
        packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE,
        artificial_latency_ms: int = 0,
    ) -> "NodeController":
        """Prepare the application components for the future runtime loop."""
        LOGGER.info("Bootstrapping node controller")
        self.role = role
        self._configure_role(
            packet_drop_rate=packet_drop_rate,
            artificial_latency_ms=artificial_latency_ms,
        )
        self._bootstrap_world()
        if role is PlayerRole.CLIENT and isinstance(self.prediction_engine, NoopPredictionEngine):
            self.prediction_engine = PredictionEngine(
                engine=self.engine,
                local_player_id=self.local_player_id,
                history_capacity=INPUT_HISTORY_SIZE,
            )
        self.lifecycle.move_to_idle()
        self.is_bootstrapped = True
        LOGGER.info(
            "Bootstrap completed: state=%s, role=%s, tick_interval=%.4f, renderer=%sx%s",
            self.lifecycle.state,
            self.role,
            self.tick_interval,
            self.renderer.width,
            self.renderer.height,
        )
        return self

    def build_runtime_context(self) -> dict[str, object]:
        """Expose the components wired by the controller."""
        context = {
            "engine": self.engine,
            "renderer": self.renderer,
            "input_handler": self.input_handler,
            "tick_interval": self.tick_interval,
            "role": self.role,
            "local_player_id": self.local_player_id,
            "remote_player_id": self.remote_player_id,
        }
        LOGGER.info("Runtime context ready: %s", ", ".join(sorted(context)))
        return context

    def process_frame(self, dt: float, local_input: InputState) -> object:
        """Advance one frame according to the current runtime role."""
        if not self.lifecycle.is_started:
            self.lifecycle.move_to_game()
        self.udp_handler.open_socket()
        if self.role is PlayerRole.HOST:
            return self._process_host_frame(dt, local_input)
        return self._process_client_frame(dt, local_input)

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
            frame_handler=self.process_frame,
            engine=self.engine,
            input_handler=self.input_handler,
            renderer=self.renderer,
            local_player_id=self.local_player_id,
        )
        app.run()
        self.udp_handler.close_socket()
        return True

    def _configure_role(self, *, packet_drop_rate: float, artificial_latency_ms: int = 0) -> None:
        """Configure ports and player identities for host or client mode."""
        if self.role is PlayerRole.HOST:
            self.local_player_id = HOST_PLAYER_ID
            self.remote_player_id = CLIENT_PLAYER_ID
            self.input_handler.control_scheme = ControlScheme.ARROWS
            self.udp_handler = UdpHandler(
                host="0.0.0.0",
                port=HOST_UDP_PORT,
                packet_drop_rate=packet_drop_rate,
                artificial_latency_ms=artificial_latency_ms,
            )
            self.remote_port = CLIENT_UDP_PORT
        else:
            self.local_player_id = CLIENT_PLAYER_ID
            self.remote_player_id = HOST_PLAYER_ID
            self.input_handler.control_scheme = ControlScheme.WASD
            self.udp_handler = UdpHandler(
                host="0.0.0.0",
                port=CLIENT_UDP_PORT,
                packet_drop_rate=packet_drop_rate,
                artificial_latency_ms=artificial_latency_ms,
            )
            self.remote_port = HOST_UDP_PORT

    def _bootstrap_world(self) -> None:
        """Ensure both local and remote players exist in the local world."""
        if self.engine.world_state.get_player(self.local_player_id) is None:
            x, y = self._spawn_position_for(self.local_player_id)
            self.engine.spawn_player(self.local_player_id, x=x, y=y)
        if self.engine.world_state.get_player(self.remote_player_id) is None:
            x, y = self._spawn_position_for(self.remote_player_id)
            self.engine.spawn_player(self.remote_player_id, x=x, y=y)

    def _spawn_position_for(self, player_id: str) -> tuple[int, int]:
        """Return a stable spawn point for each player across every process."""
        if player_id == HOST_PLAYER_ID:
            return 100, 100
        if player_id == CLIENT_PLAYER_ID:
            return 240, 100
        return 100, 100

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
