"""Application entry point for a Distributed SMB node."""

import logging

from distributed_smb.application.node_controller import NodeController


def build_controller() -> NodeController:
    """Create and bootstrap the application's central controller."""
    controller = NodeController().bootstrap()
    controller.build_runtime_context()
    return controller


def get_controller() -> NodeController:
    """Get a bootstrapped controller without starting the GUI (for testing)."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    return build_controller()


def main(*, run_app: bool = False) -> None:
    """Bootstrap the local node and start the graphical application."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logging.info("Starting Distributed SMB")
    controller = build_controller()
    if run_app:
        controller.run()
    return controller


if __name__ == "__main__":
    main(run_app=True)
