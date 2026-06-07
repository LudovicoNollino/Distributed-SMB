"""Manages the lifecycle of the lobby and game-event Docker containers."""

import subprocess
import time

from distributed_smb.shared.config import GAME_EVENT_WS_PORT, LOBBY_STARTUP_WAIT, LOBBY_WS_PORT

_IMAGE_LOBBY = "distributed-smb-lobby"
_IMAGE_GAMEEVENTS = "distributed-smb-gameevents"
_NAME_LOBBY = "smb-lobby"
_NAME_GAMEEVENTS = "smb-gameevents"


class LobbyContainerManager:
    def start(self) -> None:
        self.stop()
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "-p", f"{LOBBY_WS_PORT}:{LOBBY_WS_PORT}",
                "--name", _NAME_LOBBY,
                _IMAGE_LOBBY,
            ],
            check=True,
        )
        subprocess.run(
            [
                "docker", "run", "-d", "--rm",
                "-p", f"{GAME_EVENT_WS_PORT}:{GAME_EVENT_WS_PORT}",
                "--name", _NAME_GAMEEVENTS,
                _IMAGE_GAMEEVENTS,
            ],
            check=True,
        )
        time.sleep(LOBBY_STARTUP_WAIT)

    def stop(self) -> None:
        for name in [_NAME_LOBBY, _NAME_GAMEEVENTS]:
            subprocess.run(["docker", "stop", name], check=False, capture_output=True)
