"""Application entry point for a Distributed SMB node."""

import logging

from distributed_smb.application.node_controller import NodeController


def build_controller() -> NodeController:
    """Create and bootstrap the application's central controller."""
    controller = NodeController().bootstrap()
    controller.build_runtime_context()
    return controller


def main() -> NodeController:
    """Bootstrap the local node and return its controller."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logging.info("Starting Distributed SMB")
    return build_controller()


if __name__ == "__main__":
    main()
