"""Tests for _try_recover_session() function in main.py."""

from unittest.mock import MagicMock, patch

from distributed_smb.main import _try_recover_session
from distributed_smb.shared.session_metadata import CachedPeer, SessionMetadata


class TestTryRecoverSession:
    """Unit tests for recovery orchestration in main.py."""

    def test_no_metadata_returns_none(self):
        """With no persisted metadata, recovery returns None."""
        with patch("distributed_smb.main.read_session_metadata", return_value=None):
            result = _try_recover_session("127.0.0.1")

        assert result is None

    def test_user_closes_lobby_during_recovery_returns_none(self):
        """If user closes lobby during recovery, return None."""
        metadata = SessionMetadata(
            session_id="session-abc",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        mock_screen = MagicMock()
        mock_screen.render.return_value = False  # User closes window

        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            result = _try_recover_session("127.0.0.1", lobby_screen=mock_screen)

        assert result is None
        mock_screen.close.assert_not_called()  # Provided screen is not closed by helper

    def test_prober_finds_host_returns_host_ip_and_session_id(self):
        """When prober finds host, return (host_ip, session_id)."""
        metadata = SessionMetadata(
            session_id="session-abc",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        mock_screen = MagicMock()
        mock_screen.render.return_value = True

        mock_prober = MagicMock()
        mock_prober.find_current_host.return_value = "10.0.0.2"

        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            result = _try_recover_session(
                "127.0.0.1",
                lobby_screen=mock_screen,
                prober=mock_prober,
            )

        assert result == ("10.0.0.2", "session-abc")
        mock_prober.find_current_host.assert_called_once_with(
            "session-abc",
            "127.0.0.1",
            metadata.peers,
            timeout_per_peer=0.5,
        )

    def test_prober_fails_cleans_up_and_returns_none(self):
        """When prober finds no host, delete metadata and return None."""
        metadata = SessionMetadata(
            session_id="session-abc",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        mock_screen = MagicMock()
        mock_screen.render.return_value = True

        mock_prober = MagicMock()
        mock_prober.find_current_host.return_value = None

        deleted = []

        def fake_delete():
            deleted.append(True)

        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            with patch("distributed_smb.main.delete_session_metadata", fake_delete):
                result = _try_recover_session(
                    "127.0.0.1",
                    lobby_screen=mock_screen,
                    prober=mock_prober,
                )

        assert result is None
        assert deleted == [True]

    def test_uses_recovery_prober_by_default(self):
        """If no prober is provided, default RecoveryProber is used."""
        metadata = SessionMetadata(
            session_id="session-abc",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        mock_screen = MagicMock()
        mock_screen.render.return_value = True

        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            with patch("distributed_smb.main.RecoveryProber") as mock_prober_cls:
                mock_instance = MagicMock()
                mock_instance.find_current_host.return_value = "10.0.0.2"
                mock_prober_cls.return_value = mock_instance

                result = _try_recover_session("127.0.0.1", lobby_screen=mock_screen)

        assert result == ("10.0.0.2", "session-abc")
        mock_prober_cls.assert_called_once()

    def test_closes_screen_only_if_not_provided(self):
        """Screen is closed only if created internally, not if provided."""
        metadata = SessionMetadata(
            session_id="session-abc",
            local_player_id="player-1",
            peers=[CachedPeer(player_id="player-2", ip="127.0.0.2", join_index=1)],
        )

        # Test with provided screen
        provided_screen = MagicMock()
        provided_screen.render.return_value = True

        mock_prober = MagicMock()
        mock_prober.find_current_host.return_value = "10.0.0.2"

        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            result = _try_recover_session(
                "127.0.0.1",
                lobby_screen=provided_screen,
                prober=mock_prober,
            )

        provided_screen.close.assert_not_called()
        assert result == ("10.0.0.2", "session-abc")

        # Test with internal screen (created in function)
        with patch("distributed_smb.main.read_session_metadata", return_value=metadata):
            with patch("distributed_smb.main.LobbyScreen") as mock_screen_cls:
                mock_instance = MagicMock()
                mock_instance.render.return_value = True
                mock_screen_cls.return_value = mock_instance

                mock_prober = MagicMock()
                mock_prober.find_current_host.return_value = "10.0.0.2"

                result = _try_recover_session(
                    "127.0.0.1",
                    prober=mock_prober,
                )

        mock_instance.close.assert_called_once()
        assert result == ("10.0.0.2", "session-abc")
