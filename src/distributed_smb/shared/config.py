"""Project-wide configuration defaults."""

DEFAULT_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 50000
DEFAULT_TCP_PORT = 50001
HOST_UDP_PORT = 50010
CLIENT_UDP_PORT = 50011
UDP_MAX_PACKET_SIZE = 65535
DEFAULT_PACKET_DROP_RATE = 0.0
HOST_PLAYER_ID = "player1"
CLIENT_PLAYER_ID = "player2"

# Lobby WebSocket server
LOBBY_WS_PORT = 50002
LOBBY_WS_PATH = "/lobby"
LOBBY_WS_URL_TEMPLATE = "ws://{host}:{port}{path}"

# Game event WebSocket server (host → clients, reliable in-game events)
GAME_EVENT_WS_PORT = 50003
GAME_EVENT_WS_PATH = "/game-events"

# Player disconnect detection
UDP_INPUT_TIMEOUT = 5.0  # seconds without UDP input before a peer is considered gone
GAME_EVENT_HEARTBEAT_INTERVAL = 5.0  # seconds between WebSocket heartbeat pings

# Lobby coordination timings
LOBBY_STARTUP_WAIT = 0.5  # seconds to wait for uvicorn to bind before connecting
LOBBY_TIMEOUT = 30.0  # seconds a client waits for GAME_START before giving up

# Minimum connected peers before the host can trigger GAME_START
MIN_PLAYERS_TO_START = 2

TICK_RATE = 60
TICK_INTERVAL = 1.0 / TICK_RATE

# Remote snapshot smoothing and loss-tolerance timings.
SNAPSHOT_TIMEOUT = 0.15
MAX_EXTRAPOLATION_TIME = 0.35

# Base resolution used as logical reference.
BASE_WINDOW_WIDTH = 640
BASE_WINDOW_HEIGHT = 480

# Global world/presentation scale factor.
WORLD_SCALE = 1.5

WINDOW_WIDTH = int(BASE_WINDOW_WIDTH * WORLD_SCALE)
WINDOW_HEIGHT = int(BASE_WINDOW_HEIGHT * WORLD_SCALE)
WINDOW_TITLE = "Distributed SMB"

PLAYER_WIDTH = int(50 * WORLD_SCALE)
PLAYER_HEIGHT = int(50 * WORLD_SCALE)

MAX_PLAYERS = 4
