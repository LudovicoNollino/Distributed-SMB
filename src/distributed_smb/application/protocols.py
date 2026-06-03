"""Application-layer abstractions for network services."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GameEventBrokerProtocol(Protocol):
    def send(self, payload: bytes) -> None: ...
    def get_disconnected_player(self) -> str | None: ...
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None: ...


@runtime_checkable
class LobbyServiceProtocol(Protocol):
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None: ...


class NoopGameEventBroker:
    def send(self, payload: bytes) -> None:
        pass

    def get_disconnected_player(self) -> str | None:
        return None

    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        pass


class NoopLobbyService:
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        pass
