GRAVITY = 1000
MOVE_SPEED = 200
JUMP_FORCE = -400

def apply_physics(player, dt):
    player.vy += GRAVITY * dt
    player.x += player.vx * dt
    player.y += player.vy * dt
    