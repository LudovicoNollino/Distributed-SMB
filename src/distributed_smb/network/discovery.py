"""UDP broadcast discovery — resolves session_id → (host_ip, lobby_port) without a registry."""

import logging
import socket
import threading

from distributed_smb.shared.config import DISCOVERY_UDP_PORT

LOGGER = logging.getLogger(__name__)


def _local_ipv4_addresses() -> list[str]:
    """Return all non-loopback IPv4 addresses bound to local interfaces."""
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    return list(addresses)


class DiscoveryService:
    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def announce(self, session_id: str, lobby_port: int) -> None:
        """Listen for discovery queries and respond with lobby_port.

        The client learns host_ip from the UDP packet source address.
        """
        self._running = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_UDP_PORT))
        sock.settimeout(1.0)
        self._sock = sock

        query = f"WHO {session_id}".encode()
        response = str(lobby_port).encode()

        def _listen() -> None:
            LOGGER.info(
                "[discovery] listening on UDP :%d for session %s",
                DISCOVERY_UDP_PORT,
                session_id,
            )
            while self._running:
                try:
                    data, addr = sock.recvfrom(256)
                    if data == query:
                        LOGGER.info(
                            "[discovery] query from %s:%d → port %d",
                            addr[0],
                            addr[1],
                            lobby_port,
                        )
                        sock.sendto(response, addr)
                except TimeoutError:
                    continue
                except OSError:
                    break

        self._thread = threading.Thread(target=_listen, name="discovery-announce", daemon=True)
        self._thread.start()

    def discover(self, session_id: str, timeout: float = 5.0) -> tuple[str, int]:
        """Broadcast a discovery query and return (host_ip, lobby_port).

        The query is sent from every local IPv4 interface, not just the one
        chosen by the default route. This avoids losing the broadcast on
        machines where a virtual adapter (e.g. Docker Desktop's vEthernet)
        has a lower-metric default route than the real LAN NIC.
        """
        query = f"WHO {session_id}".encode()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as recv_sock:
            recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            recv_sock.bind(("0.0.0.0", 0))
            recv_sock.settimeout(timeout)

            LOGGER.info(
                "[discovery] broadcasting WHO %s on port %d", session_id, DISCOVERY_UDP_PORT
            )
            for local_ip in _local_ipv4_addresses():
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as send_sock:
                        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        send_sock.bind((local_ip, 0))
                        send_sock.sendto(query, ("255.255.255.255", DISCOVERY_UDP_PORT))
                except OSError:
                    continue

            data, (host_ip, _) = recv_sock.recvfrom(64)
            lobby_port = int(data.decode())
            LOGGER.info("[discovery] found host at %s, lobby port %d", host_ip, lobby_port)
            return host_ip, lobby_port

    def stop(self) -> None:
        self._running = False
        if self._sock:
            self._sock.close()
            self._sock = None
