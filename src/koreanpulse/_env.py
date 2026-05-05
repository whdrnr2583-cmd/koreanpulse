"""Load `.env` once, at package import.

Search order (first hit wins):
    1. $KOREANPULSE_ENV_FILE  (explicit override)
    2. ./.env                 (current working directory)
    3. <project_root>/.env    (this repo's root, useful when invoked from elsewhere)

Existing OS env vars are never overwritten — that's how a sysadmin or a
Claude Desktop config block can always win over a checked-out `.env`.

The loader is silent on miss. If `python-dotenv` is missing, we fall back to
a tiny inline parser so the package keeps working in barebones environments.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


_LOADED = False


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("KOREANPULSE_ENV_FILE", "").strip()
    if explicit:
        paths.append(Path(explicit))

    paths.append(Path.cwd() / ".env")

    # Walk upward from this file to find a `.env` next to pyproject.toml.
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if (ancestor / "pyproject.toml").exists():
            paths.append(ancestor / ".env")
            break

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        unique.append(p)
    return unique


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal `.env` parser. KEY=VALUE per line, # comments, quoted values OK."""
    out: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_env_once() -> None:
    """Idempotent. Safe to call from many import sites."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    for path in _candidate_paths():
        if not path.exists():
            continue

        try:
            from dotenv import load_dotenv  # type: ignore[import-not-found]
            # `override=False`: never beat real env vars
            load_dotenv(path, override=False)
            logger.debug("loaded .env via python-dotenv: %s", path)
        except ImportError:
            try:
                values = _parse_env_file(path)
            except OSError as exc:
                logger.debug("could not read %s: %s", path, exc)
                return
            for k, v in values.items():
                # Same rule: don't clobber existing env
                os.environ.setdefault(k, v)
            logger.debug("loaded .env via fallback parser: %s", path)
        return  # only load the first match
