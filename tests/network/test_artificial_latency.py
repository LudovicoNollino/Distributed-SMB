"""Unit tests for UdpHandler artificial latency simulation."""

import time

import pytest

from distributed_smb.network.udp_handler import UdpHandler

SENDER_PORT = 59600
RECEIVER_PORT = 59601
LATENCY_MS = 100
TOLERANCE = 0.030  # 30ms tolerance for scheduling jitter


@pytest.fixture(autouse=True)
def handlers():
    sender = UdpHandler(host="127.0.0.1", port=SENDER_PORT, artificial_latency_ms=LATENCY_MS)
    receiver = UdpHandler(host="127.0.0.1", port=RECEIVER_PORT)
    sender.open_socket()
    receiver.open_socket()
    yield sender, receiver
    sender.close_socket()
    receiver.close_socket()


def test_packet_not_delivered_before_latency_elapses(handlers):
    """Packet must not arrive before artificial_latency_ms has passed."""
    sender, receiver = handlers

    sender.send_packet_nowait(b"hello", "127.0.0.1", RECEIVER_PORT)

    # Check immediately — packet should still be queued
    result = receiver.receive_packet_nowait()
    assert result is None, "Packet arrived before latency elapsed"


def test_packet_delivered_after_latency_elapses(handlers):
    """Packet must arrive after artificial_latency_ms has passed."""
    sender, receiver = handlers

    sender.send_packet_nowait(b"hello", "127.0.0.1", RECEIVER_PORT)

    time.sleep((LATENCY_MS + TOLERANCE * 1000) / 1000.0)

    # Trigger flush by sending another packet (or call directly)
    sender._flush_outgoing()

    deadline = time.time() + 0.5
    received = None
    while time.time() < deadline:
        received = receiver.receive_packet_nowait()
        if received is not None:
            break
        time.sleep(0.01)

    assert received is not None, "Packet never arrived after latency elapsed"
    assert received[0] == b"hello"


def test_zero_latency_sends_immediately(handlers):
    """With artificial_latency_ms=0 packets are sent without queuing."""
    _, receiver = handlers
    direct = UdpHandler(host="127.0.0.1", port=59602, artificial_latency_ms=0)
    direct.open_socket()

    direct.send_packet_nowait(b"immediate", "127.0.0.1", RECEIVER_PORT)

    time.sleep(0.02)
    result = receiver.receive_packet_nowait()
    direct.close_socket()

    assert result is not None, "Packet with zero latency was not delivered immediately"
    assert result[0] == b"immediate"


def test_packet_ordering_preserved(handlers):
    """Multiple packets must arrive in send order after latency elapses."""
    sender, receiver = handlers

    for i in range(5):
        sender.send_packet_nowait(f"pkt-{i}".encode(), "127.0.0.1", RECEIVER_PORT)

    time.sleep((LATENCY_MS + TOLERANCE * 1000) / 1000.0)
    sender._flush_outgoing()

    received = []
    deadline = time.time() + 0.5
    while time.time() < deadline and len(received) < 5:
        pkt = receiver.receive_packet_nowait()
        if pkt:
            received.append(pkt[0])
        else:
            time.sleep(0.01)

    assert len(received) == 5
    assert received == [f"pkt-{i}".encode() for i in range(5)]
