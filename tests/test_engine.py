from domain.game_engine import GameEngine
from shared.input import InputState


def test_move_right():
    engine = GameEngine()

    initial_x = engine.player.x

    input_state = InputState(right=True)

    for _ in range(60):  # 1 secondo
        engine.apply_input(input_state)
        engine.update(1/60)

    assert engine.player.x > initial_x, "Il player non si muove a destra"