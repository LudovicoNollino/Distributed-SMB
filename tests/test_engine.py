from src.distributed_smb.domain.game_engine import GameEngine
from src.distributed_smb.shared.input import InputState

def test_move_right():
    engine = GameEngine()
    player = engine.get_local_player()
    initial_x = player.x

    input_state = InputState(right=True)

    for _ in range(60):
        engine.apply_input(input_state)
        engine.tick(1/60)

    assert player.x > initial_x, "Player did not move to the right"

def test_gravity():
    engine = GameEngine()
    player = engine.get_local_player()
    initial_y = player.y

    for _ in range(60):
        engine.tick(1/60)

    assert player.y > initial_y, "Gravity does not work"

def test_jump():
    engine = GameEngine()
    player = engine.get_local_player()

    player.on_ground = True

    input_state = InputState(jump=True)

    engine.apply_input(input_state)
    engine.tick(1/60)

    assert player.vy < 0, "Jump does not set upward velocity"

def test_landing():
    engine = GameEngine()
    player = engine.get_local_player()
    player.y = 300
    player.vy = 100

    for _ in range(120):
        engine.tick(1/60)

    assert player.on_ground is True, "Player did not land"
    assert player.vy == 0, "Vertical velocity did not reset on landing"

def test_no_input():
    engine = GameEngine()
    player = engine.get_local_player()

    initial_x = player.x

    for _ in range(60):
        engine.tick(1/60)

    assert player.x == initial_x, "Player did not stay in place without input"

def test_collision_floor():
    engine = GameEngine()
    player = engine.get_local_player()

    player.y = 0
    player.vy = 0

    for _ in range(300):
        engine.tick(1/60)

    floor_y = engine.platforms[0].y

    assert player.y + player.height == floor_y, "Collision with floor is incorrect"