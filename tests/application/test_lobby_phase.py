"""Integration tests for NodeController.lobby_phase()."""

import threading
import time
from unittest.mock import patch

import pytest

from distributed_smb.application.node_controller import NodeController
from distributed_smb.application.protocols import NoopGameEventBroker, NoopLobbyService
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
    ctrl = NodeController(
        game_event_broker=NoopGameEventBroker(),
        lobby_service=NoopLobbyService(),
    ).bootstrap(role=PlayerRole.HOST)
    ctrl.ws_handler = WsHandler(host="127.0.0.1", port=TEST_PORT)
    return ctrl


def _make_client() -> NodeController:
    ctrl = NodeController(
        game_event_broker=NoopGameEventBroker(),
        lobby_service=NoopLobbyService(),
    ).bootstrap(role=PlayerRole.CLIENT)
    ctrl.ws_handler = WsHandler(host="127.0.0.1", port=TEST_PORT)
    return ctrl


# ---------------------------------------------------------------------------
# Host-only: the host triggers the start manually, no real client needed
# ---------------------------------------------------------------------------


def test_host_lobby_phase_single_player():
    host = _make_host()

    with patch("distributed_smb.application.lobby_coordinator.time.sleep"):
        roster = host.lobby_phase(start_requested=lambda: True)

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
            with patch("distributed_smb.application.lobby_coordinator.time.sleep"):
                host.lobby_phase(start_requested=lambda: len(host.roster.players) >= 2)
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
    """A host who starts solo must see a world with only their own character."""
    host = _make_host()
    with patch("distributed_smb.application.lobby_coordinator.time.sleep"):
        host.lobby_phase(start_requested=lambda: True)

    assert set(host.engine.world_state.characters) == {"player1"}


# ---------------------------------------------------------------------------
# replay_lobby_phase(): re-entering the waiting room after a victory, without
# recreating the session (host and client are already connected).
# ---------------------------------------------------------------------------


def test_replay_lobby_phase_resets_engine_without_new_session():
    host = _make_host()
    client = _make_client()

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
    assert not errors, errors

    original_session_id = host.session_id
    host.engine.world_state.victory = True
    host.engine.world_state.victory_player_id = "player1"
    host.engine.world_state.environment.destructible_blocks[0].destroyed = True

    def replay_host():
        try:
            with patch("distributed_smb.application.lobby_coordinator.time.sleep"):
                host.replay_lobby_phase(start_requested=lambda: True)
        except Exception as exc:
            errors.append(exc)

    def replay_client():
        try:
            client.replay_lobby_phase()
        except Exception as exc:
            errors.append(exc)

    t_host = threading.Thread(target=replay_host)
    t_client = threading.Thread(target=replay_client)
    t_host.start()
    t_client.start()
    t_host.join(timeout=10.0)
    t_client.join(timeout=10.0)

    assert not errors, errors
    assert host.session_id == original_session_id
    assert client.session_id == original_session_id
    assert host.engine.world_state.victory is False
    assert host.engine.world_state.environment.destructible_blocks[0].destroyed is False
    assert set(host.engine.world_state.characters) == {"player1", "player2"}


def test_client_returns_to_menu_when_the_host_leaves_the_lobby():
    """SessionClosed must abort the client's wait with a distinct error, so
    main() can send it back to the menu instead of hanging on poll()."""
    from distributed_smb.application.lobby_coordinator import SessionClosedError
    from distributed_smb.shared.messages.session import SessionClosed

    class ClosingWsHandler:
        def poll(self):
            return SessionClosed(session_id="abc123")

    controller = NodeController().bootstrap(role=PlayerRole.CLIENT)
    controller.ws_handler = ClosingWsHandler()

    with pytest.raises(SessionClosedError):
        controller._client_replay_wait()


def _run_lobby_until_cancelled(ctrl, errors, **kwargs):
    from distributed_smb.application.lobby_coordinator import (
        LobbyCancelledError,
        SessionClosedError,
    )

    try:
        ctrl.lobby_phase(**kwargs)
    except (LobbyCancelledError, SessionClosedError) as exc:
        errors.append(exc)


def test_a_client_leaving_disappears_from_the_hosts_roster():
    """End-to-end with real controllers and sockets: a client that leaves the
    lobby must vanish from the host's roster. Guards the client side too —
    the leave message is only correct if session_id and join_index were
    recorded when the join was acknowledged, not later at game start."""
    host = _make_host()
    client = _make_client()
    stop_host = threading.Event()
    outcomes: list = []

    def host_update(status, session_id, roster):
        return not stop_host.is_set()

    t_host = threading.Thread(
        target=_run_lobby_until_cancelled,
        args=(host, outcomes),
        kwargs={"on_update": host_update, "start_requested": lambda: False},
        daemon=True,
    )
    t_host.start()
    deadline = time.time() + 5.0
    while not host.session_id and time.time() < deadline:
        time.sleep(0.05)

    stop_client = threading.Event()
    t_client = threading.Thread(
        target=_run_lobby_until_cancelled,
        args=(client, outcomes),
        kwargs={
            "session_id": host.session_id,
            "on_update": lambda *a: not stop_client.is_set(),
        },
        daemon=True,
    )
    t_client.start()

    deadline = time.time() + 5.0
    while (
        len(host.roster.players) < 2 or len(client.roster.players) < 2
    ) and time.time() < deadline:
        time.sleep(0.05)
    assert len(host.roster.players) == 2
    assert len(client.roster.players) == 2

    client.leave_lobby()
    stop_client.set()

    deadline = time.time() + 5.0
    while len(host.roster.players) != 1 and time.time() < deadline:
        time.sleep(0.05)

    stop_host.set()
    t_host.join(timeout=3.0)
    t_client.join(timeout=3.0)

    assert [p.player_id for p in host.roster.players] == ["player1"]


def test_the_host_leaving_sends_every_client_back_to_the_menu():
    """End-to-end: when the host leaves, a waiting client's lobby phase must
    end with SessionClosedError instead of waiting forever."""
    from distributed_smb.application.lobby_coordinator import SessionClosedError

    host = _make_host()
    client = _make_client()
    stop_host = threading.Event()
    outcomes: list = []

    t_host = threading.Thread(
        target=_run_lobby_until_cancelled,
        args=(host, outcomes),
        kwargs={
            "on_update": lambda *a: not stop_host.is_set(),
            "start_requested": lambda: False,
        },
        daemon=True,
    )
    t_host.start()
    deadline = time.time() + 5.0
    while not host.session_id and time.time() < deadline:
        time.sleep(0.05)

    t_client = threading.Thread(
        target=_run_lobby_until_cancelled,
        args=(client, outcomes),
        kwargs={"session_id": host.session_id},
        daemon=True,
    )
    t_client.start()

    deadline = time.time() + 5.0
    while len(client.roster.players) < 2 and time.time() < deadline:
        time.sleep(0.05)

    host.leave_lobby()
    stop_host.set()

    t_client.join(timeout=5.0)
    t_host.join(timeout=3.0)

    assert not t_client.is_alive()
    assert any(isinstance(o, SessionClosedError) for o in outcomes)
