"""koreanpulse — Korean industry intelligence MCP."""
from __future__ import annotations

# Load .env (if any) before any submodule reads os.environ.
from koreanpulse._env import load_env_once

load_env_once()

__version__ = "0.1.13"

__all__ = ["__version__", "load_env_once"]
