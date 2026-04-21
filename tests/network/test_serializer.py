from distributed_smb.domain.messages import PlayerInputPacket, WorldStateSnapshot
from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.input import InputState


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
