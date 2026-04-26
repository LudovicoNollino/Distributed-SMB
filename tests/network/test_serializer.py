import pytest

from distributed_smb.domain.messages import (
    GameStart,
    InitialStateSync,
    PlayerInputPacket,
    RosterUpdate,
    SessionCreate,
    SessionCreated,
    SessionJoin,
    SessionJoined,
    WorldStateSnapshot,
)
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.enums import ConnectionStatus
from distributed_smb.shared.input import InputState
from distributed_smb.shared.roster import GlobalRoster, RosterEntry


def test_encode_and_decode_player_input_packet():
    serializer = Serializer()
    packet = PlayerInputPacket(
        player_id="player2",
        sequence_number=7,
        input_state=InputState(left=True, jump=True),
    )

    decoded = serializer.decode_message(serializer.encode_message(packet))

    assert isinstance(decoded, PlayerInputPacket)
    assert decoded.player_id == "player2"
    assert decoded.sequence_number == 7
    assert decoded.input_state.left is True
    assert decoded.input_state.jump is True


def test_encode_and_decode_world_state_snapshot():
    serializer = Serializer()
    world_state = WorldState(
        sequence_number=3,
        characters={
            "player1": CharacterState(player_id="player1", x=10.0, y=20.0),
            "player2": CharacterState(player_id="player2", x=30.0, y=40.0),
        },
    )
    snapshot = WorldStateSnapshot(sequence_number=9, world_state=world_state)

    decoded = serializer.decode_message(serializer.encode_message(snapshot))

    assert isinstance(decoded, WorldStateSnapshot)
    assert decoded.sequence_number == 9
    assert decoded.world_state.sequence_number == 3
    assert set(decoded.world_state.characters) == {"player1", "player2"}
    assert decoded.world_state.characters["player2"].x == 30.0


# ------------------------------------------------------------------
# WebSocket coordination messages — M3
# ------------------------------------------------------------------


def test_ws_session_create_roundtrip():
    s = Serializer()
    msg = SessionCreate(player_id="p1", ip="192.168.1.1", udp_port=50010)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, SessionCreate)
    assert decoded.player_id == "p1"
    assert decoded.ip == "192.168.1.1"
    assert decoded.udp_port == 50010


def test_ws_session_created_roundtrip():
    s = Serializer()
    msg = SessionCreated(session_id="abc123", join_index=1)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, SessionCreated)
    assert decoded.session_id == "abc123"
    assert decoded.join_index == 1


def test_ws_session_join_roundtrip():
    s = Serializer()
    msg = SessionJoin(session_id="abc123", player_id="p2", ip="192.168.1.2", port=50011)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, SessionJoin)
    assert decoded.player_id == "p2"
    assert decoded.port == 50011


def test_ws_session_joined_roundtrip():
    s = Serializer()
    msg = SessionJoined(join_index=2)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, SessionJoined)
    assert decoded.join_index == 2


def test_ws_roster_update_roundtrip():
    s = Serializer()
    roster = GlobalRoster()
    roster.add_player(RosterEntry("p1", "192.168.1.1", 50010, 1, ConnectionStatus.CONNECTED, True))
    roster.add_player(RosterEntry("p2", "192.168.1.2", 50011, 2, ConnectionStatus.CONNECTED, False))
    msg = RosterUpdate(roster=roster)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, RosterUpdate)
    players = decoded.roster.get_all_players()
    assert len(players) == 2
    assert players[0].player_id == "p1"
    assert players[0].is_host is True
    assert players[1].join_index == 2
    assert players[1].status == ConnectionStatus.CONNECTED


def test_ws_game_start_roundtrip():
    s = Serializer()
    msg = GameStart(session_id="abc123")
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, GameStart)
    assert decoded.session_id == "abc123"


def test_ws_initial_state_sync_roundtrip():
    s = Serializer()
    world_state = WorldState(
        sequence_number=5,
        characters={"p1": CharacterState(player_id="p1", x=100.0, y=200.0)},
    )
    msg = InitialStateSync(world_state=world_state)
    decoded = s.decode_ws_message(s.encode_ws_message(msg))
    assert isinstance(decoded, InitialStateSync)
    assert decoded.world_state.sequence_number == 5
    assert decoded.world_state.characters["p1"].x == 100.0


def test_ws_decode_unknown_type_raises():
    s = Serializer()
    with pytest.raises(ValueError, match="Unsupported WebSocket message type"):
        s.decode_ws_message({"message_type": "unknown_type"})
