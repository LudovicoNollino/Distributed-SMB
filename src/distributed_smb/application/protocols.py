"""Application-layer abstractions for network services."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GameEventBrokerProtocol(Protocol):
    def send(self, payload: bytes) -> None: ...
    def get_disconnected_player(self) -> str | None: ...
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None: ...
    def reconnect(self, host: str, port: int) -> None: ...
    def promote_to_server(self, port: int) -> None: ...


@runtime_checkable
class LobbyServiceProtocol(Protocol):
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None: ...


@runtime_checkable
class DiscoveryServiceProtocol(Protocol):
    def announce(self, session_id: str, lobby_port: int) -> None: ...
    def discover(self, session_id: str, timeout: float = 5.0) -> tuple[str, int]: ...
    def stop(self) -> None: ...


@runtime_checkable
class LobbyContainerManagerProtocol(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class NoopGameEventBroker:
    def send(self, payload: bytes) -> None:
        pass

    def get_disconnected_player(self) -> str | None:
        return None

    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        pass

    def reconnect(self, host: str, port: int) -> None:
        pass

    def promote_to_server(self, port: int) -> None:
        pass


class NoopLobbyService:
    def launch(self, host: str = "0.0.0.0", port: int = 0) -> None:
        pass


class NoopDiscoveryService:
    def announce(self, session_id: str, lobby_port: int) -> None:
        pass

    def discover(self, session_id: str, timeout: float = 5.0) -> tuple[str, int]:
        return ("127.0.0.1", 50002)

    def stop(self) -> None:
        pass


class NoopLobbyContainerManager:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
