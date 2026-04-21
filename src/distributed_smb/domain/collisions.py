def check_collision(player, platform):
    return (
        player.x < platform.x + platform.width
        and player.x + player.width > platform.x
        and player.y < platform.y + platform.height
        and player.y + player.height > platform.y
    )


def resolve_collision(player, platform) -> None:
    """Resolve collision by finding the side with minimum overlap."""
    overlap_left = (player.x + player.width) - platform.x
    overlap_right = (platform.x + platform.width) - player.x
    overlap_top = (player.y + player.height) - platform.y
    overlap_bottom = (platform.y + platform.height) - player.y

    sides = [
        ("top", overlap_top, lambda: _resolve_top_collision(player, platform)),
        ("bottom", overlap_bottom, lambda: _resolve_bottom_collision(player, platform)),
        ("left", overlap_left, lambda: _resolve_left_collision(player, platform)),
        ("right", overlap_right, lambda: _resolve_right_collision(player, platform)),
    ]

    _, _, handler = min(sides, key=lambda s: s[1])
    handler()


def _resolve_top_collision(player, platform) -> None:
    """Caduta sulla piattaforma."""
    if player.vy > 0 and player.prev_y + player.height <= platform.y:
        player.y = platform.y - player.height
        player.vy = 0
        player.on_ground = True


def _resolve_bottom_collision(player, platform) -> None:
    """Colpo alla testa."""
    if player.vy < 0:
        player.y = platform.y + platform.height
        player.vy = 0


def _resolve_left_collision(player, platform) -> None:
    """Urto dal lato sinistro."""
    if player.vx > 0:
        player.x = platform.x - player.width
        player.vx = 0


def _resolve_right_collision(player, platform) -> None:
    """Urto dal lato destro."""
    if player.vx < 0:
        player.x = platform.x + platform.width
        player.vx = 0
