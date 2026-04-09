"""Rendering abstractions for the game client."""

from dataclasses import dataclass


@dataclass(slots=True)
class Renderer:
    """Minimal renderer placeholder for future Pygame integration."""

    width: int = 640
    height: int = 480
