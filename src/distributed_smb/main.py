"""Application entry point for a Distributed SMB node."""

import logging

from distributed_smb.application.node_controller import NodeController
from distributed_smb.presentation.app import GameApp


def build_controller() -> NodeController:
    """Create and bootstrap the application's central controller."""
    controller = NodeController().bootstrap()
    controller.build_runtime_context()
    return controller


def get_controller() -> NodeController:
    """Get a bootstrapped controller without starting the GUI (for testing)."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    return build_controller()


def main() -> None:
    """Bootstrap the local node and start the graphical application."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logging.info("Starting Distributed SMB")

    controller = build_controller()
    app = GameApp(
        engine=controller.engine,
        input_handler=controller.input_handler,
    )
    app.run()


if __name__ == "__main__":
    main()
