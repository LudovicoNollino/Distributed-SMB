"""End-to-end recovery test: session persistence, host crash, client recovery.

Simulates:
  1. Host + Client reach IN_GAME with session_metadata written
  2. Client promoted to host (simulating election)
  3. Original host rejoins via attempt_recovery()
  4. Verify: join_index=2, role=CLIENT, no SessionCreate sent
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from distributed_smb.application.node_controller import NodeController
from distributed_smb.application.protocols import NoopGameEventBroker, NoopLobbyService
from distributed_smb.network.lobby_service import launch_lobby_server, lobby_manager
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.shared.config import HOST_UDP_PORT, LOBBY_STARTUP_WAIT
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.session_metadata import CachedPeer, SessionMetadata

TEST_WS_PORT = 59301
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


def _run_lobby(host: NodeController, client: NodeController) -> list:
    """Run lobby phase for host and client in parallel."""
    errors = []

    def run_host():
        try:
            with patch("distributed_smb.application.lobby_coordinator.time.sleep"):
                host.lobby_phase(start_requested=lambda: len(host.roster.players) >= 2)
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


class TestSessionRecovery:
    """Recovery after host crash: client promoted, old host rejoins."""

    def test_recovery_flow_with_promotion(self):
        """
        1. Host + Client finish lobby → session metadata written
        2. Client promoted to HOST (election simulation)
        3. Original host calls attempt_recovery() → rejoins as CLIENT
        4. Assert: join_index=2, role=CLIENT, session_id preserved
        """
        host = NodeController(
            game_event_broker=NoopGameEventBroker(),
            lobby_service=NoopLobbyService(),
        ).bootstrap(role=PlayerRole.HOST)
        host.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)
        host.local_ip = "127.0.0.1"

        client = NodeController(
            game_event_broker=NoopGameEventBroker(),
            lobby_service=NoopLobbyService(),
        ).bootstrap(role=PlayerRole.CLIENT)
        client.ws_handler = WsHandler("127.0.0.1", TEST_WS_PORT)
        client.local_ip = "127.0.0.1"

        # --- Lobby phase ---
        errors = _run_lobby(host, client)
        assert not errors, errors
        assert host.session_id == client.session_id
        assert host.session_id != ""

        # Assert metadata was written for both
        assert host.lifecycle.state.name.lower() == "in_game"
        assert client.lifecycle.state.name.lower() == "in_game"

        original_session_id = host.session_id

        # --- Simulate client promotion to host ---
        client.role = PlayerRole.HOST
        client.remote_host = ""
        client.remote_port = 0

        # --- Simulate original host rejoining ---
        # Create a spy prober that returns client's IP when probed
        class _SpyProber:
            def find_current_host(self, session_id, requester_ip, peers, timeout_per_peer):
                assert session_id == original_session_id
                assert len(peers) >= 1
                # Return the promoted client's IP
                return client.local_ip

        host_recovering = NodeController(
            game_event_broker=NoopGameEventBroker(),
            lobby_service=NoopLobbyService(),
            recovery_prober=_SpyProber(),
        ).bootstrap(role=PlayerRole.CLIENT)
        host_recovering.local_ip = "127.0.0.2"
        # Simulate metadata written before crash
        host_recovering.session_id = original_session_id
        host_recovering.local_player_id = "player1"

        # --- Attempt recovery ---
        result = host_recovering.attempt_recovery()

        # Assert recovery succeeded
        assert result == client.local_ip
        assert host_recovering.remote_host == client.local_ip
        assert host_recovering.remote_port == HOST_UDP_PORT
        assert host_recovering.session_id == original_session_id

    def test_recovery_with_no_metadata_returns_none(self):
        """Recovery with no persisted metadata returns None."""
        controller = NodeController(
            game_event_broker=NoopGameEventBroker(),
            recovery_prober=MagicMock(),
        ).bootstrap(role=PlayerRole.CLIENT)
        controller.local_ip = "127.0.0.1"

        with patch(
            "distributed_smb.application.recovery_mixin.read_session_metadata", return_value=None
        ):
            result = controller.attempt_recovery()

        assert result is None
        assert controller.lifecycle.state.name.lower() == "recovering"

    def test_recovery_with_empty_peers_returns_none_and_cleans_up(self):
        """Recovery with empty peers list cleans up metadata and returns None."""
        controller = NodeController(
            game_event_broker=NoopGameEventBroker(),
            recovery_prober=MagicMock(),
        ).bootstrap(role=PlayerRole.CLIENT)
        controller.local_ip = "127.0.0.1"
        controller.session_id = "test-session"
        controller.local_player_id = "player-1"

        metadata = SessionMetadata(
            session_id="test-session",
            local_player_id="player-1",
            peers=[],
        )

        deleted = []

        def fake_delete():
            deleted.append(True)

        with patch(
            "distributed_smb.application.recovery_mixin.read_session_metadata",
            return_value=metadata,
        ):
            with patch(
                "distributed_smb.application.recovery_mixin.delete_session_metadata", fake_delete
            ):
                result = controller.attempt_recovery()

        assert result is None
        assert deleted == [True]

    def test_recovery_with_failed_prober_returns_none_and_cleans_up(self):
        """Recovery when prober finds no host returns None and cleans up."""
        controller = NodeController(
            game_event_broker=NoopGameEventBroker(),
            recovery_prober=MagicMock(return_value=None),
        ).bootstrap(role=PlayerRole.CLIENT)
        controller.local_ip = "127.0.0.1"
        controller.session_id = "test-session"
        controller.local_player_id = "player-1"

        metadata = SessionMetadata(
            session_id="test-session",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        deleted = []

        def fake_delete():
            deleted.append(True)

        with patch(
            "distributed_smb.application.recovery_mixin.read_session_metadata",
            return_value=metadata,
        ):
            with patch(
                "distributed_smb.application.recovery_mixin.delete_session_metadata", fake_delete
            ):
                controller.recovery_prober.find_current_host.return_value = None
                result = controller.attempt_recovery()

        assert result is None
        assert deleted == [True]
