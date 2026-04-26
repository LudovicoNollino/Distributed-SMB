"""WebSocket client for lobby coordination."""

import asyncio
import json
import queue
import threading
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from distributed_smb.network.serializer import Serializer, WsMessage
from distributed_smb.shared.config import LOBBY_WS_PATH, LOBBY_WS_URL_TEMPLATE

_serializer = Serializer()


@dataclass(slots=True)
class WsHandler:
    """WebSocket client that bridges the async lobby server and the sync game loop.

    The connection runs in a background daemon thread with its own asyncio event
    loop. Incoming messages are decoded and placed on `inbox`; the game loop
    reads them via `poll()` without ever blocking. Outgoing messages are sent
    via `send()`, which is safe to call from any thread.
    """

    host: str
    port: int
    inbox: queue.Queue = field(default_factory=queue.Queue)
    _loop: Any = field(default=None, init=False, repr=False)
    _ws: Any = field(default=None, init=False, repr=False)
    _thread: Any = field(default=None, init=False, repr=False)

    def _url(self) -> str:
        return LOBBY_WS_URL_TEMPLATE.format(host=self.host, port=self.port, path=LOBBY_WS_PATH)

    def connect(self, timeout: float = 10.0) -> None:
        """Open the connection in a background daemon thread.

        Blocks until the handshake completes or `timeout` seconds elapse.
        """
        ready = threading.Event()

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._receive_loop(ready))

        self._thread = threading.Thread(target=_run, name="ws-client", daemon=True)
        self._thread.start()
        ready.wait(timeout=timeout)

    async def _receive_loop(self, ready: threading.Event) -> None:
        async with ws_connect(self._url()) as ws:
            self._ws = ws
            ready.set()
            async for raw in ws:
                try:
                    msg = _serializer.decode_ws_message(json.loads(raw))
                    self.inbox.put(msg)
                except Exception:
                    pass

    def send(self, message: WsMessage) -> None:
        """Send a coordination message from the game loop thread (thread-safe)."""
        if self._loop is None or self._ws is None:
            raise RuntimeError("WsHandler not connected — call connect() first")
        payload = json.dumps(_serializer.encode_ws_message(message))
        future = asyncio.run_coroutine_threadsafe(self._ws.send(payload), self._loop)
        future.result(timeout=5.0)

    def poll(self) -> WsMessage | None:
        """Non-blocking read from the inbox; returns None if no message is waiting."""
        try:
            return self.inbox.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        """Close the WebSocket connection and wait for the background thread to exit."""
        if self._loop is not None and self._ws is not None:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
