"""Project-wide configuration defaults."""

DEFAULT_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 50000
DEFAULT_TCP_PORT = 50001
HOST_UDP_PORT = 50010
CLIENT_UDP_PORT = 50011
UDP_MAX_PACKET_SIZE = 65535
DEFAULT_PACKET_DROP_RATE = 0.0
HOST_PLAYER_ID = "player1"


def player_id_for(join_index: int) -> str:
    """Return the canonical player ID for the given lobby join order (0-based)."""
    return f"player{join_index + 1}"

# Lobby WebSocket server
LOBBY_WS_PORT = 50002
LOBBY_WS_PATH = "/lobby"
LOBBY_WS_URL_TEMPLATE = "ws://{host}:{port}{path}"

# Game event WebSocket server (host → clients, reliable in-game events)
GAME_EVENT_WS_PORT = 50003
GAME_EVENT_WS_PATH = "/game-events"

# Session discovery (UDP broadcast)
DISCOVERY_UDP_PORT = 59099

# Player disconnect detection
UDP_INPUT_TIMEOUT = 5.0  # seconds without UDP input before a peer is considered gone
GAME_EVENT_HEARTBEAT_INTERVAL = 5.0  # seconds between WebSocket heartbeat pings

# Lobby coordination timings
LOBBY_STARTUP_WAIT = 0.5  # seconds to wait for uvicorn to bind before connecting
LOBBY_TIMEOUT = 30.0  # seconds a client waits for GAME_START before giving up

TICK_RATE = 60
TICK_INTERVAL = 1.0 / TICK_RATE
DIVERGENCE_THRESHOLD = 5.0

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

# ---------------------------------------------------------------------------
# M5 — client-side prediction and reconciliation
# ---------------------------------------------------------------------------
#
# LAN tuning guide (one-way latency measured with ping):
#
#   Condition          RTT        DIVERGENCE_THRESHOLD   ARTIFICIAL_LATENCY_MS
#   -----------------------------------------------------------------------
#   Stable LAN         1–5 ms     10.0 px                0   (disabled)
#   Average LAN        5–20 ms    20.0 px  ← default      0   (disabled)
#   Noisy LAN         20–50 ms    35.0 px                0   (disabled)
#   Simulated lag     any         20.0 px                50–200 ms (testing only)
#
# DIVERGENCE_THRESHOLD: positional error (px) above which the client rolls
# back to the authoritative state and replays buffered inputs. Lower values
# give a more authoritative feel but trigger more rollbacks on a noisy link;
# higher values feel smoother but tolerate more visual desync.
DIVERGENCE_THRESHOLD: float = 20.0

# INPUT_HISTORY_SIZE: number of frames kept in the circular input buffer for
# post-rollback replay. At 60 fps this covers 1 second of history, which is
# more than enough for any realistic LAN round-trip time.
INPUT_HISTORY_SIZE: int = 60

# MAX_ROLLBACK_FRAMES: hard cap on how many frames can be replayed in a single
# reconciliation step. Prevents unbounded CPU spikes if the host goes silent
# for a long time and then sends a very old authoritative snapshot.
MAX_ROLLBACK_FRAMES: int = 30

# PREDICTION_LEAD_EWMA_ALPHA: smoothing factor for the running average of how
# many predicted-but-unacknowledged ticks the client is ahead of the host
# (its "prediction lead"). This average tracks the network's true round-trip
# latency in ticks, which drifts slowly if at all.
PREDICTION_LEAD_EWMA_ALPHA: float = 0.01

# PREDICTION_LEAD_DRIFT_TOLERANCE: how many ticks the instantaneous prediction
# lead may deviate from its running average before the client adjusts its tick
# rate by one tick (skip a tick if running ahead, double-tick if running
# behind). This corrects clock drift between client and host without
# fighting the baseline lead caused by genuine round-trip latency, keeping
# the lead bounded over long sessions.
PREDICTION_LEAD_DRIFT_TOLERANCE: float = 3.0

# RECONCILE_GLIDE_RATE: fraction of the outstanding visual reconciliation
# error absorbed per frame. Combined with RECONCILE_MAX_GLIDE_PX below, small
# errors (a few px, the normal one-tick prediction jitter) resolve in 1-2
# frames, while large errors (a jump-timing mismatch, tens of px) resolve in
# a handful of frames at the capped rate instead of lingering for ~1s.
RECONCILE_GLIDE_RATE: float = 0.3

# RECONCILE_MAX_GLIDE_PX: hard cap, in pixels per frame, on how much of the
# outstanding error is absorbed in a single frame. Bounds the worst-case
# visible jolt for very large corrections regardless of their size.
RECONCILE_MAX_GLIDE_PX: float = 8.0

# ARTIFICIAL_LATENCY_MS: one-way delay injected by UdpHandler on outgoing
# packets. Use only for local testing of reconciliation behaviour; must be
# 0 in production.
ARTIFICIAL_LATENCY_MS: int = 0
