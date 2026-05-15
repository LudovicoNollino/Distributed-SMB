from dataclasses import dataclass

from distributed_smb.domain.session import GameSession
from distributed_smb.shared.enums import SessionPhase


@dataclass(slots=True)
class SessionState:
    session_info: GameSession
    phase: SessionPhase = SessionPhase.WAITING

    def move_to_waiting_room(self) -> None:
        self.phase = SessionPhase.WAITING

    def start(self) -> None:
        self.phase = SessionPhase.PLAYING

    def end(self) -> None:
        self.phase = SessionPhase.ENDED

    @property
    def is_waiting_room(self) -> bool:
        return self.phase is SessionPhase.WAITING

    @property
    def is_started(self) -> bool:
        return self.phase is SessionPhase.PLAYING
