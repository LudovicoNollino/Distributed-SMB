"""Container entrypoint: uvicorn distributed_smb.network.game_event_server_main:app --port 50003."""

from distributed_smb.network.game_events.server import app

__all__ = ["app"]
