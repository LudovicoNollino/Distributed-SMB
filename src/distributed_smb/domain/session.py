"""Session aggregate definitions."""

from dataclasses import dataclass, field
from datetime import datetime

from distributed_smb.shared.enums import PlayerRole, SessionPhase
from distributed_smb.shared.roster import GlobalRoster


@dataclass(slots=True)
class SessionInfo:
    """Logical session metadata accessible by lobby and peers."""

    session_id: str
    host_player_id: str
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1  # For future migration support


@dataclass(slots=True)
class HostMigrationMetadata:
    """Metadata for tracking host migration state."""

    current_host_player_id: str
    previous_host_player_id: str | None = None
    election_in_progress: bool = False
    election_candidate_ids: list[str] = field(default_factory=list)
    migration_version: int = 0


@dataclass(slots=True)
class PeerRejoinMetadata:
    """Metadata for handling peer reconnection and state recovery."""

    last_heartbeat_from: dict[str, datetime] = field(default_factory=dict)
    disconnected_peers: set[str] = field(default_factory=set)
    handshake_tokens: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class GameSession:
    """Represents the lifecycle of a multiplayer match."""

    session_id: str
    host_player_id: str | None = None
    roster: GlobalRoster = field(default_factory=GlobalRoster)
    state: SessionPhase = SessionPhase.WAITING
    local_role: PlayerRole = PlayerRole.CLIENT
    session_info: SessionInfo | None = None
    migration_metadata: HostMigrationMetadata | None = None
    rejoin_metadata: PeerRejoinMetadata | None = None

    def initialize_session_info(self):
        """Create SessionInfo from current state (called by session owner)."""
        if self.host_player_id:
            self.session_info = SessionInfo(
                session_id=self.session_id,
                host_player_id=self.host_player_id,
            )

    def initialize_migration_metadata(self):
        """Initialize host migration tracking."""
        if self.host_player_id:
            self.migration_metadata = HostMigrationMetadata(
                current_host_player_id=self.host_player_id
            )

    def initialize_rejoin_metadata(self):
        """Initialize peer rejoin tracking."""
        self.rejoin_metadata = PeerRejoinMetadata()
