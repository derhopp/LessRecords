"""Lightweight HA stub for pure options-flow unit tests.

The full HA runtime integration tests are tracked separately. Unit tests
here never touch a production Recorder database.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def hass():
    """Provide the minimal mock Home Assistant API used in options tests."""
    return MagicMock()
