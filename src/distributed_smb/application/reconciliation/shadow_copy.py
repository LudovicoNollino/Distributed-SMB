"""ShadowCopy protocol and no-op implementation.

ShadowCopy smooths the visual representation of remote entities between
authoritative snapshots. Each remote player gets its own ShadowCopy
instance, initialised after lobby and updated on every snapshot arrival.

Persona 2 delivers the real interpolation/extrapolation logic; until then
NoopShadowCopy acts as a transparent pass-through (returns the last known
state unchanged).
"""

from typing import Protocol, runtime_checkable

from distributed_smb.domain.world import CharacterState


@runtime_checkable
class ShadowCopyProtocol(Protocol):
    """Manages the display state for one remote entity."""

    def update(self, state: CharacterState) -> None:
        """Record a new authoritative state from an incoming snapshot."""
        ...

    def get_display_state(self) -> CharacterState | None:
        """Return the state to render, potentially interpolated or extrapolated.

        Returns None if no snapshot has arrived yet for this entity.
        """
        ...


class NoopShadowCopy:
    """Pass-through — stores the last known state and returns it unchanged.

    Preserves current rendering behaviour until Persona 2 delivers the
    real interpolation implementation.
    """

    def __init__(self) -> None:
        self._state: CharacterState | None = None

    def update(self, state: CharacterState) -> None:
        self._state = state

    def get_display_state(self) -> CharacterState | None:
        return self._state
