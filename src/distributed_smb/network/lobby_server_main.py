"""Standalone entrypoint for the lobby service.

Run with:
    uvicorn distributed_smb.network.lobby_server_main:app --host 0.0.0.0 --port 50002
"""

from distributed_smb.network.lobby.service import app

__all__ = ["app"]
