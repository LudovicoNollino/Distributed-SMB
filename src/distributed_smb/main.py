"""Application entry point for a Distributed SMB node."""

from distributed_smb.application.node_controller import NodeController


def main() -> None:
    """Bootstrap the local node controller."""
    controller = NodeController()
    controller.bootstrap()


if __name__ == "__main__":
    main()
