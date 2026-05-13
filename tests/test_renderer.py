import pygame

from distributed_smb.domain.world import CharacterState, WorldState
from distributed_smb.presentation.renderer import Renderer


def test_renderer_draws_sprite_instead_of_flat_background(monkeypatch):
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 0)
    screen = pygame.display.set_mode((200, 200))
    renderer = Renderer(width=200, height=200)
    world = WorldState(
        characters={
            "player1": CharacterState(
                player_id="player1",
                x=40,
                y=30,
                width=50,
                height=50,
                on_ground=True,
            )
        }
    )

    renderer.render(screen=screen, world_state=world, platforms=[])

    sprite_pixels = [
        screen.get_at((x, y))[:3]
        for x in range(40, 90)
        for y in range(30, 80)
    ]
    assert any(pixel != renderer.background_color for pixel in sprite_pixels)


def test_renderer_preserves_last_facing_direction_when_player_stops(monkeypatch):
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 0)
    screen = pygame.display.set_mode((200, 200))
    renderer = Renderer(width=200, height=200)
    character = CharacterState(
        player_id="player1",
        x=40,
        y=30,
        width=50,
        height=50,
        vx=-10,
        on_ground=True,
    )
    world = WorldState(characters={"player1": character})

    renderer.render(screen=screen, world_state=world, platforms=[])
    assert renderer._facing_by_player["player1"] == -1

    character.vx = 0
    renderer.render(screen=screen, world_state=world, platforms=[])
    assert renderer._facing_by_player["player1"] == -1


def test_walk_animation_uses_distinct_frames(monkeypatch):
    renderer = Renderer()
    character = CharacterState(
        player_id="player1",
        width=50,
        height=50,
        vx=10,
        on_ground=True,
    )

    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 0)
    frame_a = pygame.image.tobytes(renderer._get_player_sprite(character), "RGBA")

    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 160)
    frame_b = pygame.image.tobytes(renderer._get_player_sprite(character), "RGBA")

    assert frame_a != frame_b
