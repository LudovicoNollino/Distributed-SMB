"""Orchestrates presentation, domain, and network components."""

import importlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.domain.lifecycle import NodeLifecycle
from distributed_smb.domain.messages import (
    GameStart,
    PlayerInputPacket,
    RosterUpdate,
    SessionCreate,
    SessionCreated,
    SessionJoin,
    SessionJoined,
    WorldStateSnapshot,
)
from distributed_smb.network.lobby_service import launch_lobby_server
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
    HOST_PLAYER_ID,
    HOST_UDP_PORT,
    LOBBY_STARTUP_WAIT,
    LOBBY_TIMEOUT,
    LOBBY_WS_PORT,
    MIN_PLAYERS_TO_START,
    TICK_INTERVAL,
)
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.input import InputState
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
        default_factory=lambda: WsHandler(host=DEFAULT_HOST, port=LOBBY_WS_PORT)
    )
    session_id: str = ""
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

    def bootstrap(
        self,
        *,
        role: PlayerRole = PlayerRole.HOST,
        packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE,
    ) -> "NodeController":
        """Prepare the application components for the future runtime loop."""
        LOGGER.info("Bootstrapping node controller")
        self.role = role
        self._configure_role(packet_drop_rate=packet_drop_rate)
        self._bootstrap_world()
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
        """Expose the components wired by the controller.

        This keeps the bootstrap contract explicit while the concrete game loop
        is still being implemented in the next integration step.
        """
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

    def lobby_phase(
        self,
        *,
        session_id: str = "",
        min_players: int = MIN_PLAYERS_TO_START,
    ) -> GlobalRoster:
        """Run the lobby coordination phase before gameplay begins.

        HOST: starts the lobby server, registers itself, waits for enough
        players, then broadcasts GameStart.
        CLIENT: joins the session identified by `session_id` and waits for
        the GameStart broadcast from the host.
        """
        if self.role is PlayerRole.HOST:
            self._host_lobby_phase(min_players=min_players)
        else:
            self._client_lobby_phase(session_id=session_id)
        self._rebuild_world_from_roster()
        return self.roster

    def _host_lobby_phase(self, *, min_players: int) -> GlobalRoster:
        launch_lobby_server(port=LOBBY_WS_PORT)
        time.sleep(LOBBY_STARTUP_WAIT)

        self.ws_handler.connect()
        self.ws_handler.send(
            SessionCreate(
                player_id=self.local_player_id,
                ip=self.udp_handler.host,
                udp_port=self.udp_handler.port,
            )
        )

        created: SessionCreated = self._poll_lobby(SessionCreated)
        self.session_id = created.session_id
        LOGGER.info("Session created: %s", self.session_id)

        deadline = time.time() + LOBBY_TIMEOUT
        while time.time() < deadline:
            msg = self.ws_handler.poll()
            if isinstance(msg, RosterUpdate):
                self.roster = msg.roster
                if len(self.roster.players) >= min_players:
                    break
            time.sleep(0.05)

        self.ws_handler.send(GameStart(session_id=self.session_id))
        self._poll_lobby(GameStart)
        LOGGER.info("Lobby phase complete: %d players", len(self.roster.players))

    def _client_lobby_phase(self, *, session_id: str) -> None:
        self.ws_handler.connect()
        self.ws_handler.send(
            SessionJoin(
                session_id=session_id,
                player_id=self.local_player_id,
                ip=self.udp_handler.host,
                port=self.udp_handler.port,
            )
        )

        self._poll_lobby(SessionJoined)

        deadline = time.time() + LOBBY_TIMEOUT
        while time.time() < deadline:
            msg = self.ws_handler.poll()
            if isinstance(msg, RosterUpdate):
                self.roster = msg.roster
            elif isinstance(msg, GameStart):
                self.session_id = msg.session_id
                break
            time.sleep(0.05)

        LOGGER.info("Lobby phase complete: session=%s", self.session_id)

    def _poll_lobby(self, expected_type: type, timeout: float = LOBBY_TIMEOUT) -> Any:
        """Block until a specific message type arrives on the WsHandler inbox."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.ws_handler.poll()
            if msg is None:
                time.sleep(0.05)
                continue
            if isinstance(msg, RosterUpdate):
                self.roster = msg.roster
            if isinstance(msg, expected_type):
                return msg
        raise TimeoutError(f"Lobby timeout waiting for {expected_type.__name__}")

    def _rebuild_world_from_roster(self) -> None:
        """Clear world state and spawn only the players confirmed in the roster."""
        self.engine.world_state.characters.clear()
        for entry in self.roster.get_all_players():
            x, y = self._spawn_position_for(entry.player_id)
            self.engine.spawn_player(entry.player_id, x=x, y=y)
        others = [
            e.player_id
            for e in self.roster.get_all_players()
            if e.player_id != self.local_player_id
        ]
        if others:
            self.remote_player_id = others[0]

    def _configure_role(self, *, packet_drop_rate: float) -> None:
        """Configure ports and player identities for host or client mode."""
        if self.role is PlayerRole.HOST:
            self.local_player_id = HOST_PLAYER_ID
            self.remote_player_id = CLIENT_PLAYER_ID
            self.input_handler.control_scheme = ControlScheme.ARROWS
            self.udp_handler = UdpHandler(
                host=DEFAULT_HOST,
                port=HOST_UDP_PORT,
                packet_drop_rate=packet_drop_rate,
            )
            self.remote_port = CLIENT_UDP_PORT
        else:
            self.local_player_id = CLIENT_PLAYER_ID
            self.remote_player_id = HOST_PLAYER_ID
            self.input_handler.control_scheme = ControlScheme.WASD
            self.udp_handler = UdpHandler(
                host=DEFAULT_HOST,
                port=CLIENT_UDP_PORT,
                packet_drop_rate=packet_drop_rate,
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

    def _drain_remote_input_packets(self) -> None:
        """Poll incoming client input packets and cache the latest valid ones."""
        while True:
            packet = self.udp_handler.receive_packet_nowait()
            if packet is None:
                return
            payload, _address = packet
            decoded = self.serializer.decode_message(payload)
            if not isinstance(decoded, PlayerInputPacket):
                continue

            last_sequence = self.last_remote_input_sequence.get(decoded.player_id, -1)
            if decoded.sequence_number <= last_sequence:
                continue

            self.last_remote_input_sequence[decoded.player_id] = decoded.sequence_number
            self.cached_remote_inputs[decoded.player_id] = decoded.input_state
            self.received_input_packets += 1

    def _drain_snapshot_packets(self) -> None:
        """Poll incoming snapshots and keep only the newest authoritative state."""
        while True:
            packet = self.udp_handler.receive_packet_nowait()
            if packet is None:
                return
            payload, _address = packet
            decoded = self.serializer.decode_message(payload)
            if not isinstance(decoded, WorldStateSnapshot):
                continue
            if decoded.sequence_number <= self.last_snapshot_sequence:
                continue

            self.last_snapshot_sequence = decoded.sequence_number
            self.engine.world_state = decoded.world_state
            self.received_snapshots += 1

    def _build_host_inputs(self, local_input: InputState) -> dict[str, InputState]:
        """Combine local and remote input streams into one authoritative map."""
        return {
            self.local_player_id: local_input,
            self.remote_player_id: self.cached_remote_inputs.get(
                self.remote_player_id,
                InputState(),
            ),
        }

    def _send_world_state_snapshot(self) -> None:
        """Broadcast the authoritative world state to the remote client."""
        snapshot = WorldStateSnapshot(
            sequence_number=self.engine.world_state.sequence_number,
            world_state=self.engine.world_state,
        )
        payload = self.serializer.encode_message(snapshot)
        self.udp_handler.send_packet_nowait(payload, self.remote_host, self.remote_port)
        self.sent_snapshots += 1

    def _send_input_packet(self, local_input: InputState) -> None:
        """Send the local client's input packet to the authoritative host."""
        self.input_sequence_number += 1
        packet = PlayerInputPacket(
            player_id=self.local_player_id,
            sequence_number=self.input_sequence_number,
            input_state=local_input,
        )
        payload = self.serializer.encode_message(packet)
        self.udp_handler.send_packet_nowait(payload, self.remote_host, self.remote_port)
        self.sent_input_packets += 1

    def process_frame(self, dt: float, local_input: InputState) -> object:
        """Advance one frame according to the current runtime role."""
        self.udp_handler.open_socket()

        if self.role is PlayerRole.HOST:
            self._drain_remote_input_packets()
            authoritative_inputs = self._build_host_inputs(local_input)
            self.engine.tick(dt, authoritative_inputs)
            self._send_world_state_snapshot()
            return self.engine.world_state

        self._send_input_packet(local_input)
        self.engine.tick(dt, {self.local_player_id: local_input})
        self._drain_snapshot_packets()
        return self.engine.world_state
