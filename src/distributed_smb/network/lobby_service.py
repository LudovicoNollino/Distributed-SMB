"""Lobby service abstractions."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class LobbyService:
    """Minimal in-memory session registry placeholder."""

    known_sessions: dict[str, str] = field(default_factory=dict)
