"""Orchestrates presentation, domain, and network components."""

from dataclasses import dataclass, field

from distributed_smb.domain.lifecycle import NodeLifecycle
from distributed_smb.network.lobby_service import LobbyService
from distributed_smb.network.serializer import Serializer
from distributed_smb.network.udp_handler import UdpHandler
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.presentation.input_handler import InputHandler
from distributed_smb.presentation.renderer import Renderer
from distributed_smb.shared.config import DEFAULT_HOST, DEFAULT_TCP_PORT, DEFAULT_UDP_PORT
from distributed_smb.shared.roster import GlobalRoster


@dataclass(slots=True)
class NodeController:
    """Coordinates the node runtime without embedding domain logic."""

    lifecycle: NodeLifecycle = field(default_factory=NodeLifecycle)
    roster: GlobalRoster = field(default_factory=GlobalRoster)
    renderer: Renderer = field(default_factory=Renderer)
    input_handler: InputHandler = field(default_factory=InputHandler)
    udp_handler: UdpHandler = field(
        default_factory=lambda: UdpHandler(host=DEFAULT_HOST, port=DEFAULT_UDP_PORT)
    )
    ws_handler: WsHandler = field(
        default_factory=lambda: WsHandler(host=DEFAULT_HOST, port=DEFAULT_TCP_PORT)
    )
    lobby_service: LobbyService = field(default_factory=LobbyService)
    serializer: Serializer = field(default_factory=Serializer)

    def bootstrap(self) -> None:
        """Prepare the node for future role-specific flows."""
        self.lifecycle.move_to_idle()
