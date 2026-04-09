"""Shared enumerations used across the project."""

from enum import StrEnum


class PlayerRole(StrEnum):
    """Possible runtime roles for a node/player."""

    HOST = "host"
    CLIENT = "client"


class SessionState(StrEnum):
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
