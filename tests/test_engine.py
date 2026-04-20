from distributed_smb.domain.game_engine import GameEngine
from distributed_smb.shared.input import InputState


def test_move_right():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]
    initial_x = player.x

    input_state = InputState(right=True)

    for _ in range(60):
        engine.tick(1 / 60, {"player1": input_state})

    assert player.x > initial_x, "Player did not move to the right"


def test_gravity():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]

    initial_y = player.y

    for _ in range(60):
        engine.tick(1 / 60, {"player1": InputState()})

    assert player.y > initial_y, "Gravity does not work"


def test_jump():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]

    player.on_ground = True

    input_state = InputState(jump=True)

    engine.tick(1 / 60, {"player1": input_state})

    assert player.vy < 0, "Jump does not set upward velocity"


def test_landing():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]

    player.y = 300
    player.vy = 100

    for _ in range(120):
        engine.tick(1 / 60, {"player1": InputState()})

    assert player.on_ground is True, "Player did not land"
    assert player.vy == 0, "Vertical velocity did not reset on landing"


def test_no_input():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]

    initial_x = player.x

    for _ in range(60):
        engine.tick(1 / 60, {"player1": InputState()})

    assert player.x == initial_x, "Player did not stay in place without input"


def test_collision_floor():
    engine = GameEngine()
    engine.spawn_player("player1")
    players = engine.world_state.get_all_players()
    player = players[0]

    player.y = 0
    player.vy = 0

    for _ in range(300):
        engine.tick(1 / 60, {"player1": InputState()})

    floor_y = engine.platforms[0].y

    assert player.y + player.height == floor_y, "Collision with floor is incorrect"


def test_multiplayer_inputs():
    engine = GameEngine()
    engine.spawn_player("p1")
    engine.spawn_player("p2")

    inputs = {"p1": InputState(right=True), "p2": InputState(left=True)}

    engine.tick(0.016, inputs)

    p1 = engine.world_state.get_player("p1")
    p2 = engine.world_state.get_player("p2")

    assert p1.vx > 0
    assert p2.vx < 0
