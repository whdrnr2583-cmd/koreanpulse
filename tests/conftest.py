"""Shared test fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_backoff(monkeypatch):
    """Retry logic is exercised for real, but without sleeping through the
    production backoff delays."""
    import koreanpulse.dart as dart_mod

    monkeypatch.setattr(dart_mod, "_RETRY_BASE_SECONDS", 0.0)
