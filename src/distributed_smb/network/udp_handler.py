"""UDP transport helpers for the M2 loopback milestone."""

import asyncio
import random
import socket
from dataclasses import dataclass, field

from distributed_smb.shared.config import DEFAULT_PACKET_DROP_RATE, UDP_MAX_PACKET_SIZE


@dataclass(slots=True)
class UdpHandler:
    """Own one UDP endpoint and expose async plus immediate polling helpers."""

    host: str
    port: int
    packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE
    max_packet_size: int = UDP_MAX_PACKET_SIZE
    _socket: socket.socket | None = field(init=False, default=None, repr=False)

    def open_socket(self) -> None:
        """Bind the UDP socket if it is not already open."""
        if self._socket is not None:
            return
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind((self.host, self.port))
        udp_socket.setblocking(False)
        self._socket = udp_socket

    def close_socket(self) -> None:
        """Close the underlying UDP socket."""
        if self._socket is None:
            return
        self._socket.close()
        self._socket = None

    def _should_drop_packet(self) -> bool:
        return random.random() < self.packet_drop_rate

    async def send_packet(self, payload: bytes, remote_host: str, remote_port: int) -> None:
        """Send one UDP packet asynchronously."""
        self.open_socket()
        if self._should_drop_packet():
            return
        assert self._socket is not None
        loop = asyncio.get_running_loop()
        await loop.sock_sendto(self._socket, payload, (remote_host, remote_port))

    async def receive_packet(
        self,
        *,
        timeout: float | None = None,
    ) -> tuple[bytes, tuple[str, int]] | None:
        """Receive one UDP packet asynchronously."""
        self.open_socket()
        assert self._socket is not None
        loop = asyncio.get_running_loop()
        try:
            if timeout is None:
                packet = await loop.sock_recvfrom(self._socket, self.max_packet_size)
            else:
                packet = await asyncio.wait_for(
                    loop.sock_recvfrom(self._socket, self.max_packet_size),
                    timeout=timeout,
                )
        except TimeoutError:
            return None
        except ConnectionResetError:
            # On Windows, sending UDP packets to a peer that is not listening can
            # surface here as a connection reset on the next recv call.
            return None

        if self._should_drop_packet():
            return None
        return packet

    def send_packet_nowait(self, payload: bytes, remote_host: str, remote_port: int) -> None:
        """Send one UDP packet immediately from the game loop thread."""
        self.open_socket()
        if self._should_drop_packet():
            return
        assert self._socket is not None
        self._socket.sendto(payload, (remote_host, remote_port))

    def receive_packet_nowait(self) -> tuple[bytes, tuple[str, int]] | None:
        """Poll the socket once without blocking."""
        self.open_socket()
        assert self._socket is not None
        try:
            packet = self._socket.recvfrom(self.max_packet_size)
        except BlockingIOError:
            return None
        except ConnectionResetError:
            # On Windows, sending UDP packets to a peer that is not listening can
            # surface here as a connection reset on the next recv call.
            return None

        if self._should_drop_packet():
            return None
        return packet
