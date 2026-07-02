import socket

from distributed_smb.network.discovery import DiscoveryService
from distributed_smb.shared.config import DISCOVERY_UDP_PORT


def test_announce_only_responds_to_allowlisted_peer_ips():
    service = DiscoveryService()
    service.announce("session-abc", 50002, allowed_ips={"127.0.0.1"})

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.sendto(b"WHO session-abc", ("127.0.0.1", DISCOVERY_UDP_PORT))
            data, addr = sock.recvfrom(64)
            assert data == b"50002"
            assert addr[0] == "127.0.0.1"

        service.set_allowed_ips({"203.0.113.1"})
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            sock.sendto(b"WHO session-abc", ("127.0.0.1", DISCOVERY_UDP_PORT))
            try:
                sock.recvfrom(64)
            except TimeoutError:
                pass
            else:
                raise AssertionError("unexpected response from disallowed peer")
    finally:
        service.stop()
