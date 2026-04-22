from dataclasses import dataclass
from enum import Enum

from distributed_smb.domain.session import GameSession
from distributed_smb.shared.enums import SessionPhase

@dataclass(slots=True)
class SessionState:
    session_info: GameSession
    phase: SessionPhase = SessionPhase.WAITING