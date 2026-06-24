"""Election and host failure detection module.

Provides distributed algorithms for:
- Host failure detection (eventually perfect failure detector via timeout)
- Host election (staggered timers, deterministic ordering via JoinIndex)
- Cascading fallback on multi-node crash
"""

from distributed_smb.application.election.coordinator import (
    ElectionCoordinator,
    ElectionEvent,
    ElectionState,
    FollowingHost,
    SelfElected,
)
from distributed_smb.application.election.env_state_buffer import EnvironmentalStateBuffer
from distributed_smb.application.election.timeout_watcher import HostTimeoutWatcher

__all__ = [
    "HostTimeoutWatcher",
    "ElectionCoordinator",
    "ElectionState",
    "ElectionEvent",
    "SelfElected",
    "FollowingHost",
    "EnvironmentalStateBuffer",
]
