"""ShadowCopy wiring: init after lobby, update on snapshot, feed the renderer."""

import time
from unittest.mock import patch

from distributed_smb.application.node_controller import NodeController
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.messages.sync import WorldStateSnapshot


def _make_client_controller() -> NodeController:
    ctrl = NodeController()
    ctrl.bootstrap(role=PlayerRole.CLIENT)
    # Simulate post-lobby world: host (player1) and local client (player2) are both present.
    ctrl.remote_player_id = "player1"
    ctrl.engine.spawn_player("player1", x=100, y=100)
    return ctrl


def test_shadow_copies_exist_only_on_a_client_and_only_for_remote_players():
    """The host sees everyone locally: interpolating its own view would only
    add latency."""
    client = _make_client_controller()
    client._init_shadow_copies()
    assert client.remote_player_id in client.shadow_copies
    assert client.local_player_id not in client.shadow_copies

    host = NodeController().bootstrap(role=PlayerRole.HOST)
    host._init_shadow_copies()
    assert host.shadow_copies == {}


def _make_snapshot(seq: int, characters: dict) -> WorldStateSnapshot:
    return WorldStateSnapshot(
        sequence_number=seq,
        world_state=WorldState(sequence_number=seq, characters=characters),
    )


def test_an_arriving_snapshot_updates_both_the_engine_and_the_interpolation():
    """And one that does not mention the remote player leaves it untouched."""
    ctrl = _make_client_controller()
    ctrl._init_shadow_copies()

    host_state = CharacterState(player_id=ctrl.remote_player_id, x=50, y=100)
    payload = ctrl.serializer.encode_message(
        _make_snapshot(seq=1, characters={ctrl.remote_player_id: host_state})
    )
    with patch(
        "distributed_smb.network.udp_handler.UdpHandler.receive_packet_nowait",
        side_effect=[(payload, ("127.0.0.1", 9999)), None],
    ):
        ctrl._drain_snapshot_packets()

    assert ctrl.engine.world_state.characters[ctrl.remote_player_id].x == 50
    assert ctrl.shadow_copies[ctrl.remote_player_id].get_display_state().x == 50

    empty = _make_client_controller()
    empty._init_shadow_copies()
    empty._update_shadow_copies(_make_snapshot(1, {}))
    assert empty.shadow_copies[empty.remote_player_id].get_display_state() is None


def test_the_remote_is_shown_from_the_engine_until_interpolation_has_data():
    """What the player sees is smoothed; what the simulation replays is not."""
    ctrl = _make_client_controller()
    ctrl._init_shadow_copies()
    original_chars = dict(ctrl.engine.world_state.characters)

    local_state = ctrl.engine.world_state.characters[ctrl.local_player_id]
    display = ctrl._build_visual_world_state()

    assert display.characters[ctrl.local_player_id] is local_state
    assert ctrl.remote_player_id in display.characters  # from the engine, for now
    assert display.sequence_number == ctrl.engine.world_state.sequence_number

    interpolated = CharacterState(player_id=ctrl.remote_player_id, x=150, y=100)
    ctrl.shadow_copies[ctrl.remote_player_id].update(interpolated, sequence_number=1)

    display = ctrl._build_visual_world_state()

    assert display.characters[ctrl.remote_player_id].x == interpolated.x
    assert display.characters[ctrl.remote_player_id].y == interpolated.y
    assert ctrl.engine.world_state.characters == original_chars


def test_the_local_player_is_shown_while_alive_and_hidden_while_respawning():
    """reconcile() can drop the local player from the engine for a frame: it
    must keep being drawn, unless it is actually dead and waiting to respawn."""
    ctrl = _make_client_controller()
    ctrl._init_shadow_copies()
    local_state = ctrl.engine.world_state.characters[ctrl.local_player_id]
    del ctrl.engine.world_state.characters[ctrl.local_player_id]

    display = ctrl._build_visual_world_state(local_visual_state=local_state)
    assert display.characters[ctrl.local_player_id] is local_state

    ctrl.engine.world_state.respawn_timers[ctrl.local_player_id] = time.time() + 10.0

    display = ctrl._build_visual_world_state(local_visual_state=local_state)
    assert ctrl.local_player_id not in display.characters
    assert ctrl.local_player_id in display.respawn_timers
