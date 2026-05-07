"""Shared enumerations used across the project."""

from enum import StrEnum


class PlayerRole(StrEnum):
    """Possible runtime roles for a node/player."""

    HOST = "host"
    CLIENT = "client"


class SessionPhase(StrEnum):
    """Session lifecycle states."""

    WAITING = "waiting"
    PLAYING = "playing"
    ENDED = "ended"


class NodeState(StrEnum):
    """Local node lifecycle states."""

    IDLE = "idle"
    IN_LOBBY = "in_lobby"
    IN_GAME = "in_game"
    ELECTION = "election"
    RECOVERING = "recovering"


class ConnectionStatus(StrEnum):
    """Connectivity states for a remote peer."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class MessageType(StrEnum):
    """Message types exchanged over UDP (gameplay) and WebSocket (coordination)."""

    # UDP — high-frequency gameplay
    PLAYER_INPUT = "player_input"
    WORLD_STATE = "world_state"

    # WebSocket — lobby coordination (client → lobby)
    SESSION_CREATE = "session_create"
    SESSION_JOIN = "session_join"
    GAME_START = "game_start"
    INITIAL_STATE_SYNC = "initial_state_sync"

    # WebSocket — lobby coordination (lobby → client)
    SESSION_CREATED = "session_created"
    SESSION_JOINED = "session_joined"
    ROSTER_UPDATE = "roster_update"

    BLOCK_DESTROYED_EVENT = "block_destroyed_event"
    POWERUP_COLLECTED_EVENT = "powerup_collected_event"
    GATE_STATE_CHANGED_EVENT = "gate_state_changed_event"
    PLAYER_LEFT = "player_left"
    PLAYER_DISCONNECTED = "player_disconnected"
