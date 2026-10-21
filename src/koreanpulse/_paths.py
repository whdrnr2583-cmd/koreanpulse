"""Where koreanpulse keeps its local state (corp-code index, caches, cost log).

Resolution order:
    1. $KOREANPULSE_DATA_DIR            (explicit)
    2. ./.data                          (the long-standing default)
    3. ~/.koreanpulse                   (when the working directory is not writable)
    4. <system temp>/koreanpulse        (last resort)

Step 3 matters for MCP clients: Claude Desktop and several other hosts launch
the server with a working directory such as `/` or an app bundle that the
user cannot write to. Before this fallback the server died at import time
with `PermissionError: '.data'` and the client only showed "server
disconnected".
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_RESOLVED: Path | None = None


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def data_dir() -> Path:
    """Return the (created, writable) state directory; resolved once."""
    global _RESOLVED
    if _RESOLVED is not None:
        return _RESOLVED

    explicit = os.environ.get("KOREANPULSE_DATA_DIR", "").strip()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates += [
        Path(".data"),
        Path.home() / ".koreanpulse",
        Path(tempfile.gettempdir()) / "koreanpulse",
    ]
    for i, cand in enumerate(candidates):
        if _writable_dir(cand):
            if i > 0:
                logger.warning("state directory: using %s (earlier choices not writable)", cand)
            _RESOLVED = cand
            return cand
    raise OSError(
        "koreanpulse: no writable state directory. Set KOREANPULSE_DATA_DIR "
        "to a directory you can write to."
    )
