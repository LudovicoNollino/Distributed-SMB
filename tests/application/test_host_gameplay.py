from distributed_smb.application.node_controller import NodeController
from distributed_smb.network.serializer import Serializer
from distributed_smb.shared.input import InputState
from distributed_smb.shared.messages.gameplay import PlayerInputPacket
from distributed_smb.shared.messages.recovery import HostDiscoveryProbe, HostIdentityResponse


class FakeUdpHandler:
    def __init__(self, packets):
        self._packets = list(packets)
        self.sent = []

    def open_socket(self):
        pass

    def send_packet_nowait(self, payload, remote_host, remote_port):
        self.sent.append((payload, remote_host, remote_port))

    def receive_packet_nowait(self):
        if not self._packets:
            return None
        return self._packets.pop(0)


def test_host_discovery_probe_is_replied_to_with_host_identity_response():
    controller = NodeController()
    controller.session_id = "session-abc"
    controller.local_ip = "10.0.0.1"
    controller.udp_handler = FakeUdpHandler(
        [
            (
                Serializer().encode_message(
                    HostDiscoveryProbe(session_id="session-abc", requester_ip="127.0.0.5")
                ),
                ("127.0.0.5", 50010),
            )
        ]
    )

    drained = controller._drain_remote_input_packets()

    assert drained == 0
    assert len(controller.udp_handler.sent) == 1
    payload, remote_host, remote_port = controller.udp_handler.sent[0]
    assert remote_host == "127.0.0.5"
    assert remote_port == 50010

    response = controller.serializer.decode_message(payload)
    assert isinstance(response, HostIdentityResponse)
    assert response.session_id == "session-abc"
    assert response.host_ip == "10.0.0.1"


def test_host_discovery_probe_with_wrong_session_id_is_ignored():
    controller = NodeController()
    controller.session_id = "session-abc"
    controller.local_ip = "10.0.0.1"
    controller.udp_handler = FakeUdpHandler(
        [
            (
                Serializer().encode_message(
                    HostDiscoveryProbe(session_id="other-session", requester_ip="127.0.0.5")
                ),
                ("127.0.0.5", 50010),
            )
        ]
    )

    drained = controller._drain_remote_input_packets()

    assert drained == 0
    assert controller.udp_handler.sent == []


def test_host_discovery_probe_and_player_input_are_processed_in_same_cycle():
    controller = NodeController()
    controller.session_id = "session-abc"
    controller.local_ip = "10.0.0.1"
    controller.udp_handler = FakeUdpHandler(
        [
            (
                Serializer().encode_message(
                    HostDiscoveryProbe(session_id="session-abc", requester_ip="127.0.0.5")
                ),
                ("127.0.0.5", 50010),
            ),
            (
                Serializer().encode_message(
                    PlayerInputPacket(
                        player_id="player2",
                        sequence_number=1,
                        input_state=InputState(left=True),
                    )
                ),
                ("127.0.0.5", 50010),
            ),
        ]
    )

    drained = controller._drain_remote_input_packets()

    assert drained == 1
    assert len(controller.udp_handler.sent) == 1

    payload, remote_host, remote_port = controller.udp_handler.sent[0]
    response = controller.serializer.decode_message(payload)
    assert isinstance(response, HostIdentityResponse)
    assert response.host_ip == "10.0.0.1"
    assert controller.cached_remote_inputs["player2"].left is True
    assert controller.last_remote_input_sequence["player2"] == 1
