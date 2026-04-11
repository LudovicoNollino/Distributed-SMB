def check_collision(player, platform):
    return (
        player.x < platform.x + platform.width and
        player.x + player.width > platform.x and
        player.y < platform.y + platform.height and
        player.y + player.height > platform.y
    )