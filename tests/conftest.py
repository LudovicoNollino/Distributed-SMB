import os

import pygame
import pytest


@pytest.fixture(autouse=True, scope="session")
def initialize_pygame():
    """Initialize pygame for tests to avoid 'video system not initialized'."""
    # Set dummy display driver to avoid opening actual windows
    os.environ["SDL_VIDEODRIVER"] = "dummy"

    # Initialize pygame
    pygame.init()

    yield

    # Clean up
    pygame.quit()
