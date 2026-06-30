import socket
import threading
from typing import Optional

import pytest

from distributed_smb.application.protocols import NoopRecoveryProber, RecoveryProberProtocol
from distributed_smb.application.recovery.prober import RecoveryProber
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.messages.recovery import HostIdentityResponse
from distributed_smb.shared.session_metadata import CachedPeer


class _UdpResponder(threading.Thread):
    def __init__(self, session_id: str, host_ip: str, bind_port: int, bind_ip: str = "127.0.0.1"):
        super().__init__(daemon=True)
        self.session_id = session_id
        self.host_ip = host_ip
        self.bind_port = bind_port
        self.bind_ip = bind_ip
        self.ready = threading.Event()
        self._socket: Optional[socket.socket] = None

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bind_ip, self.bind_port))
        self._socket = sock
        self.ready.set()
        try:
            sock.settimeout(2.0)
            data, addr = sock.recvfrom(4096)
            response = Serializer().encode_message(
                HostIdentityResponse(session_id=self.session_id, host_ip=self.host_ip)
            )
            sock.sendto(response, addr)
        except TimeoutError:
            pass
        finally:
            sock.close()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_recovery_prober_returns_first_responsive_host(monkeypatch):
    port = _find_free_port()
    monkeypatch.setattr("distributed_smb.application.recovery.prober.HOST_UDP_PORT", port)

    responder = _UdpResponder(session_id="session-abc", host_ip="10.0.0.1", bind_port=port)
    responder.start()
    assert responder.ready.wait(1.0)

    prober = RecoveryProber()
    peers = [
        CachedPeer(player_id="p1", ip="127.0.0.1", join_index=0),
        CachedPeer(player_id="p2", ip="127.0.0.2", join_index=1),
    ]

    result = prober.find_current_host("session-abc", "127.0.0.5", peers, timeout_per_peer=0.5)

    assert result == "10.0.0.1"
    responder.join(1.0)


def test_recovery_prober_skips_first_unresponsive_peer_and_returns_second(monkeypatch):
    port = _find_free_port()
    monkeypatch.setattr("distributed_smb.application.recovery.prober.HOST_UDP_PORT", port)

    responder = _UdpResponder(session_id="session-abc", host_ip="10.0.0.2", bind_port=port)
    responder.start()
    assert responder.ready.wait(1.0)

    prober = RecoveryProber()
    peers = [
        CachedPeer(player_id="p1", ip="127.0.0.2", join_index=0),
        CachedPeer(player_id="p2", ip="127.0.0.1", join_index=1),
    ]

    result = prober.find_current_host("session-abc", "127.0.0.5", peers, timeout_per_peer=0.5)

    assert result == "10.0.0.2"
    responder.join(1.0)


def test_recovery_prober_returns_none_when_no_peers_respond():
    prober = RecoveryProber()
    peers = [CachedPeer(player_id="p1", ip="127.0.0.2", join_index=0)]

    result = prober.find_current_host("session-abc", "127.0.0.5", peers, timeout_per_peer=0.1)

    assert result is None


def test_recovery_prober_ignores_mismatched_session_id(monkeypatch):
    port = _find_free_port()
    monkeypatch.setattr("distributed_smb.application.recovery.prober.HOST_UDP_PORT", port)

    responder = _UdpResponder(session_id="other-session", host_ip="10.0.0.3", bind_port=port)
    responder.start()
    assert responder.ready.wait(1.0)

    prober = RecoveryProber()
    peers = [CachedPeer(player_id="p1", ip="127.0.0.1", join_index=0)]

    result = prober.find_current_host("session-abc", "127.0.0.5", peers, timeout_per_peer=0.5)

    assert result is None
    responder.join(1.0)


def test_recovery_prober_empty_peer_list_performs_no_io(monkeypatch):
    def fail_socket(*args, **kwargs):
        raise AssertionError("socket.socket should not be created for empty peers")

    monkeypatch.setattr("distributed_smb.application.recovery.prober.socket.socket", fail_socket)

    prober = RecoveryProber()
    assert prober.find_current_host("session-abc", "127.0.0.5", [], timeout_per_peer=0.1) is None


def test_noop_recovery_prober_satisfies_protocol():
    assert isinstance(NoopRecoveryProber(), RecoveryProberProtocol)
