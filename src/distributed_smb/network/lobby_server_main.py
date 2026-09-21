"""Container entrypoint: uvicorn distributed_smb.network.lobby_server_main:app --port 50002."""

from distributed_smb.network.lobby.service import app

__all__ = ["app"]
