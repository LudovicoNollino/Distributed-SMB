"""Application entry point for a Distributed SMB node."""

import argparse
import logging

from distributed_smb.application.node_controller import NodeController
from distributed_smb.network.ws_handler import WsHandler
from distributed_smb.shared.config import DEFAULT_HOST, DEFAULT_PACKET_DROP_RATE, LOBBY_WS_PORT
from distributed_smb.shared.enums import PlayerRole


def build_controller(
    *,
    role: PlayerRole = PlayerRole.HOST,
    packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE,
) -> NodeController:
    """Create and bootstrap the application's central controller."""
    controller = NodeController().bootstrap(role=role, packet_drop_rate=packet_drop_rate)
    controller.build_runtime_context()
    return controller


def get_controller(
    *,
    role: PlayerRole = PlayerRole.HOST,
    packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE,
) -> NodeController:
    """Get a bootstrapped controller without starting the GUI (for testing)."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    return build_controller(role=role, packet_drop_rate=packet_drop_rate)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line options for the loopback host/client runtime."""
    parser = argparse.ArgumentParser(description="Distributed SMB node")
    role_group = parser.add_mutually_exclusive_group()
    role_group.add_argument("--host", action="store_true", help="Run the authoritative host")
    role_group.add_argument("--client", action="store_true", help="Run the remote client")
    parser.add_argument(
        "--drop-rate",
        type=_drop_rate,
        default=DEFAULT_PACKET_DROP_RATE,
        help="Artificial UDP packet loss probability in [0.0, 1.0]",
    )
    parser.add_argument(
        "--host-ip",
        type=str,
        default=DEFAULT_HOST,
        help="IP address of the host machine (client uses this to reach the lobby)",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default="",
        help="Session ID to join (required when running as client)",
    )
    return parser.parse_args(argv)


def main(
    *,
    run_app: bool = False,
    role: PlayerRole = PlayerRole.HOST,
    packet_drop_rate: float = DEFAULT_PACKET_DROP_RATE,
    host_ip: str = DEFAULT_HOST,
    session_id: str = "",
) -> NodeController:
    """Bootstrap the local node and start the graphical application."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logging.info("Starting Distributed SMB in %s mode", role)
    controller = build_controller(role=role, packet_drop_rate=packet_drop_rate)

    if role is PlayerRole.CLIENT:
        controller.remote_host = host_ip
        controller.ws_handler = WsHandler(host=host_ip, port=LOBBY_WS_PORT)

    if run_app:
        controller.lobby_phase(session_id=session_id)
        controller.run()
    return controller


def _drop_rate(value: str) -> float:
    """Validate that the drop rate is a float in [0.0, 1.0]."""
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {value!r}")
    if not (0.0 <= f <= 1.0):
        raise argparse.ArgumentTypeError(f"must be in [0.0, 1.0], got {f}")
    return f


if __name__ == "__main__":
    args = parse_args()
    selected_role = PlayerRole.CLIENT if args.client else PlayerRole.HOST
    main(
        run_app=True,
        role=selected_role,
        packet_drop_rate=args.drop_rate,
        host_ip=args.host_ip,
        session_id=args.session_id,
    )
