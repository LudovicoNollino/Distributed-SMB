"""Pygame lobby screen shown before the gameplay loop starts."""

from dataclasses import dataclass, field

import pygame

from distributed_smb.shared.config import WINDOW_HEIGHT, WINDOW_WIDTH
from distributed_smb.shared.enums import PlayerRole
from distributed_smb.shared.roster import GlobalRoster


@dataclass(slots=True)
class LobbyScreen:
    """Render lobby status, session id, and roster while WebSocket setup runs."""

    width: int = WINDOW_WIDTH
    height: int = WINDOW_HEIGHT
    background_color: tuple[int, int, int] = (24, 28, 36)
    panel_color: tuple[int, int, int] = (38, 45, 58)
    text_color: tuple[int, int, int] = (235, 239, 245)
    muted_text_color: tuple[int, int, int] = (160, 170, 185)
    accent_color: tuple[int, int, int] = (96, 180, 140)
    error_color: tuple[int, int, int] = (235, 105, 105)
    _screen: pygame.Surface = field(init=False, repr=False)
    _title_font: pygame.font.Font = field(init=False, repr=False)
    _body_font: pygame.font.Font = field(init=False, repr=False)
    _small_font: pygame.font.Font = field(init=False, repr=False)
    is_closed: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Distributed SMB - Lobby")
        self._title_font = pygame.font.Font(None, 48)
        self._body_font = pygame.font.Font(None, 30)
        self._small_font = pygame.font.Font(None, 24)

    def render(
        self,
        *,
        role: PlayerRole,
        status: str,
        session_id: str,
        roster: GlobalRoster,
    ) -> bool:
        """Draw the current lobby view and return False if the user closed it."""
        if self.is_closed:
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_closed = True
                return False

        self._screen.fill(self.background_color)
        self._draw_text("Distributed SMB Lobby", self._title_font, self.text_color, 48, 44)
        self._draw_text(f"Role: {role.value.upper()}", self._body_font, self.accent_color, 52, 104)
        self._draw_text(status, self._body_font, self.text_color, 52, 144)

        session_label = session_id if session_id else "waiting for session id"
        self._draw_panel(52, 200, self.width - 104, 112)
        self._draw_text("Session ID", self._small_font, self.muted_text_color, 78, 222)
        self._draw_text(session_label, self._body_font, self.text_color, 78, 256)

        self._draw_panel(52, 344, self.width - 104, 270)
        self._draw_text("Roster", self._body_font, self.text_color, 78, 370)
        entries = roster.get_all_players()
        if not entries:
            self._draw_text(
                "No players connected yet",
                self._small_font,
                self.muted_text_color,
                78,
                418,
            )
        else:
            for index, entry in enumerate(entries):
                marker = "HOST" if entry.is_host else "CLIENT"
                line = (
                    f"{entry.join_index}. {entry.player_id}  "
                    f"{marker}  {entry.host}:{entry.udp_port}"
                )
                y = 418 + index * 34
                self._draw_text(line, self._small_font, self.text_color, 78, y)

        pygame.display.flip()
        return True

    def show_error(self, *, title: str, message: str) -> None:
        """Keep an error view open until the user closes the window."""
        pygame.display.set_caption("Distributed SMB - Lobby Error")
        clock = pygame.time.Clock()
        while not self.is_closed:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_closed = True
                    break

            self._screen.fill(self.background_color)
            self._draw_text(title, self._title_font, self.error_color, 48, 72)
            self._draw_panel(52, 150, self.width - 104, 220)
            self._draw_wrapped_text(
                message,
                self._body_font,
                self.text_color,
                78,
                182,
                self.width - 156,
                34,
            )
            self._draw_text(
                "Close this window to exit",
                self._small_font,
                self.muted_text_color,
                78,
                410,
            )
            pygame.display.flip()
            clock.tick(30)

    def close(self) -> None:
        """Close the lobby display surface before the gameplay app takes over."""
        pygame.display.quit()

    def _draw_panel(self, x: int, y: int, width: int, height: int) -> None:
        pygame.draw.rect(
            self._screen,
            self.panel_color,
            pygame.Rect(x, y, width, height),
            border_radius=8,
        )

    def _draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        x: int,
        y: int,
    ) -> None:
        surface = font.render(text, True, color)
        self._screen.blit(surface, (x, y))

    def _draw_wrapped_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        x: int,
        y: int,
        max_width: int,
        line_height: int,
    ) -> None:
        words = text.split()
        line = ""
        current_y = y
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if font.size(candidate)[0] <= max_width:
                line = candidate
                continue
            if line:
                self._draw_text(line, font, color, x, current_y)
                current_y += line_height
            line = word
        if line:
            self._draw_text(line, font, color, x, current_y)
