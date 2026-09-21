"""Standalone entrypoint for the game event server.

Run with:
    uvicorn distributed_smb.network.game_event_server_main:app --host 0.0.0.0 --port 50003
"""

from distributed_smb.network.game_events.server import app

__all__ = ["app"]
