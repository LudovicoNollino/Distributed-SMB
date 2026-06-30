"""Application-layer abstractions for network services."""

from typing import Protocol, runtime_checkable

from distributed_smb.shared.session_metadata import CachedPeer


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
class RecoveryProberProtocol(Protocol):
    def find_current_host(
        self,
        session_id: str,
        requester_ip: str,
        peers: list[CachedPeer],
        timeout_per_peer: float,
    ) -> str | None: ...


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


class NoopRecoveryProber:
    def find_current_host(
        self,
        session_id: str,
        requester_ip: str,
        peers: list[CachedPeer],
        timeout_per_peer: float,
    ) -> str | None:
        return None


class NoopLobbyContainerManager:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
