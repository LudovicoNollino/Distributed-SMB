"""Standalone entrypoint for the game event server.

Run with:
    uvicorn distributed_smb.network.game_event_server_main:app --host 0.0.0.0 --port 59100
"""

from distributed_smb.network.game_event_server import app

__all__ = ["app"]
