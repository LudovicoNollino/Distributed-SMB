"""HTTP-based GameEventBroker — forwards events to the containerised game-event server."""

import httpx

from distributed_smb.shared.config import GAME_EVENT_WS_PORT


class HttpGameEventBroker:
    """Sends game events via HTTP POST to the game-event container."""

    def __init__(self, host: str = "localhost", port: int = GAME_EVENT_WS_PORT) -> None:
        self._url = f"http://{host}:{port}/events"

    def send(self, payload: bytes) -> None:
        try:
            httpx.post(self._url, content=payload, timeout=1.0)
        except Exception:
            pass

    def get_disconnected_player(self) -> str | None:
        return None  # M8: add GET /disconnections endpoint

    def launch(self, host: str = "0.0.0.0", port: int = GAME_EVENT_WS_PORT) -> None:
        pass  # container lifecycle managed by LobbyContainerManager
