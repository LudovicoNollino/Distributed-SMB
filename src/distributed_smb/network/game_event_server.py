"""Game event WebSocket server — reliable in-game event delivery from host to clients."""

import asyncio
import json
import queue
import threading

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from distributed_smb.shared.config import GAME_EVENT_WS_PATH, GAME_EVENT_WS_PORT

_connections: list[WebSocket] = []
_ws_to_player: dict[int, str] = {}  # id(ws) → player_id
_disconnect_queue: queue.Queue[str] = queue.Queue()
_loop: asyncio.AbstractEventLoop | None = None

app = FastAPI(title="Distributed SMB Game Events")


@app.websocket(GAME_EVENT_WS_PATH)
async def game_event_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    player_id: str | None = None
    _connections.append(ws)
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)
        player_id = data.get("player_id")
        if player_id:
            _ws_to_player[id(ws)] = player_id

        async for _ in ws.iter_text():
            pass
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _connections:
            _connections.remove(ws)
        pid = _ws_to_player.pop(id(ws), None)
        if pid:
            _disconnect_queue.put(pid)


async def _broadcast(payload: bytes) -> None:
    text = payload.decode("utf-8")
    for ws in list(_connections):
        try:
            await ws.send_text(text)
        except Exception:
            pass


def send_game_event(payload: bytes) -> None:
    """Send an encoded game event to all connected clients (thread-safe)."""
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(payload), _loop)


def get_disconnected_player() -> str | None:
    """Return a player_id that just disconnected, or None if the queue is empty."""
    try:
        return _disconnect_queue.get_nowait()
    except queue.Empty:
        return None


def reset() -> None:
    """Clear all state — used in tests."""
    _connections.clear()
    _ws_to_player.clear()
    while not _disconnect_queue.empty():
        _disconnect_queue.get_nowait()


def launch_game_event_server(
    host: str = "0.0.0.0", port: int = GAME_EVENT_WS_PORT
) -> threading.Thread:
    """Start the game event server in a background daemon thread."""

    def _run() -> None:
        global _loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _loop = loop
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=_run, name="game-event-server", daemon=True)
    thread.start()
    return thread
