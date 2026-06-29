"""Manages the lifecycle of the lobby and game-event Docker containers."""

import logging
import subprocess
import time

from distributed_smb.shared.config import GAME_EVENT_WS_PORT, LOBBY_STARTUP_WAIT, LOBBY_WS_PORT

LOGGER = logging.getLogger(__name__)

_IMAGE_LOBBY = "distributed-smb-lobby"
_IMAGE_GAMEEVENTS = "distributed-smb-gameevents"
_NAME_LOBBY = "smb-lobby"
_NAME_GAMEEVENTS = "smb-gameevents"

_CONTAINERS = [
    (_NAME_LOBBY, _IMAGE_LOBBY, LOBBY_WS_PORT),
    (_NAME_GAMEEVENTS, _IMAGE_GAMEEVENTS, GAME_EVENT_WS_PORT),
]


class LobbyContainerManager:
    def start(self) -> None:
        self.stop()
        for name, image, port in _CONTAINERS:
            result = subprocess.run(
                ["docker", "run", "-d", "--rm", "-p", f"{port}:{port}", "--name", name, image],
                capture_output=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")
                if "already in use" in stderr:
                    # Peer already started this container — reuse it.
                    LOGGER.warning("container %s already running (peer started it) — reusing", name)
                else:
                    LOGGER.error("failed to start container %s: %s", name, stderr)
                    raise subprocess.CalledProcessError(
                        result.returncode, result.args, result.stderr
                    )
        time.sleep(LOBBY_STARTUP_WAIT)

    def stop(self) -> None:
        for name in [_NAME_LOBBY, _NAME_GAMEEVENTS]:
            subprocess.run(["docker", "stop", name], check=False, capture_output=True)
