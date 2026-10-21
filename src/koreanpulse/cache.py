"""Cache abstraction.

Translations and DART corp-code lookups are deterministic — same input always
produces the same output — so caching them aggressively is the entire reason
this product can sustain 96%+ gross margin at $0.06 per call.

Filing-list responses are *quasi*-deterministic: same query → same result for
a few minutes (new filings could appear), but historical date ranges are
effectively immutable. So entries get a per-entry TTL.

Design: small Protocol so we can swap file-based for Redis/Postgres later
without rewriting callers.

`FileCache` writes one JSON object per line to `.data/cache/<namespace>.jsonl`.
Reads load the whole file into memory once per namespace (lazy). Expired
entries get filtered on read. When a namespace file is loaded and more than
half of its lines are dead (expired or superseded), it is rewritten with only
the live entries — otherwise the 60-second "today" filing entries would grow
the file without bound over a long-lived install.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from koreanpulse._paths import data_dir

logger = logging.getLogger(__name__)


def cache_key(*parts: Any) -> str:
    """Build a stable hash key from arbitrary parts.

    >>> cache_key("translate", "ko", "en", "삼성전자")  # doctest: +ELLIPSIS
    'translate:...'
    """
    head = str(parts[0]) if parts else "default"
    payload = json.dumps(
        [str(p) for p in parts[1:]], ensure_ascii=False, sort_keys=True
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{head}:{digest}"


class Cache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None: ...


class NullCache(Cache):
    """No-op cache. Use when you want to bypass caching (testing, debugging)."""

    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        return None


class FileCache(Cache):
    """File-based JSONL cache, namespaced, with optional per-entry TTL.

    Storage format (one entry per line):
        {"k": <key>, "v": <value>, "ts": <ISO8601>, "exp": <unix-epoch or null>}

    `exp` null = never expires (default for translations / corp-code).
    `exp` set  = treat as expired once `time.time() > exp`, return None.

    Expired and superseded lines are dropped by `_compact` the next time the
    namespace file is loaded (process start), so the file stays bounded.

    Thread-safe within a single asyncio loop via an asyncio.Lock per instance.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        # Default: <state dir>/cache (see koreanpulse._paths — falls back to
        # ~/.koreanpulse when the working directory is read-only).
        self._root = Path(root) if root is not None else data_dir() / "cache"
        self._root.mkdir(parents=True, exist_ok=True)
        # store[namespace][key] = {"v": value, "exp": float|None}
        self._stores: dict[str, dict[str, dict[str, Any]]] = {}
        self._loaded: set[str] = set()
        # Lines currently in each namespace file (to compact a long-running
        # process too, not only at start-up).
        self._lines: dict[str, int] = {}
        self._compact_at: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _path(self, namespace: str) -> Path:
        return self._root / f"{namespace}.jsonl"

    def _ensure_loaded(self, namespace: str) -> dict[str, dict[str, Any]]:
        if namespace in self._loaded:
            return self._stores.setdefault(namespace, {})
        store: dict[str, dict[str, Any]] = {}
        path = self._path(namespace)
        total_lines = 0
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        total_lines += 1
                        try:
                            row = json.loads(line)
                            # Later writes for the same key win (append-only log replay)
                            store[row["k"]] = {
                                "v": row["v"],
                                "exp": row.get("exp"),
                            }
                        except (json.JSONDecodeError, KeyError) as exc:
                            logger.debug("cache: skipping malformed line: %s", exc)
            except OSError as exc:
                logger.warning("cache: failed to load %s: %s", path, exc)
            else:
                total_lines = self._compact(path, store, total_lines)
        self._lines[namespace] = total_lines
        self._stores[namespace] = store
        self._loaded.add(namespace)
        return store

    @classmethod
    def _compact(cls, path: Path, store: dict[str, dict[str, Any]], total_lines: int) -> int:
        """Drop expired entries from `store` and rewrite `path` with the
        survivors when at least half of its lines were dead weight. Returns
        the resulting line count."""
        for k in [k for k, e in store.items() if cls._is_expired(e)]:
            del store[k]
        if total_lines < 200 or len(store) * 2 > total_lines:
            return total_lines
        try:
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.stem + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    for k, e in store.items():
                        f.write(json.dumps({"k": k, "v": e["v"], "exp": e["exp"]},
                                           ensure_ascii=False) + "\n")
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
            logger.info("cache: compacted %s (%d -> %d lines)", path.name, total_lines, len(store))
            return len(store)
        except OSError as exc:
            logger.warning("cache: compaction of %s failed (%s)", path, exc)
            return total_lines

    @staticmethod
    def _is_expired(entry: dict[str, Any]) -> bool:
        exp = entry.get("exp")
        if exp is None:
            return False
        return time.time() > float(exp)

    async def get(self, key: str) -> Optional[Any]:
        namespace = key.split(":", 1)[0] if ":" in key else "default"
        async with self._lock:
            store = self._ensure_loaded(namespace)
            entry = store.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                # Drop in-memory; on-disk line will be superseded by next set().
                store.pop(key, None)
                return None
            return entry["v"]

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store a value, optionally expiring after ttl_seconds.

        ttl_seconds=None → never expires (default).
        ttl_seconds=0    → effectively never cached (will be expired on read).
        """
        namespace = key.split(":", 1)[0] if ":" in key else "default"
        exp: Optional[float] = None
        if ttl_seconds is not None:
            exp = time.time() + float(ttl_seconds)

        async with self._lock:
            store = self._ensure_loaded(namespace)
            store[key] = {"v": value, "exp": exp}
            try:
                line = json.dumps(
                    {
                        "k": key,
                        "v": value,
                        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "exp": exp,
                    },
                    ensure_ascii=False,
                )
                with self._path(namespace).open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
                self._lines[namespace] = self._lines.get(namespace, 0) + 1
                if self._lines[namespace] >= self._compact_at.get(namespace, 500):
                    self._lines[namespace] = self._compact(
                        self._path(namespace), store, self._lines[namespace]
                    )
                    # Next check once the file has doubled past its live set
                    # (avoids rescanning the store on every write).
                    self._compact_at[namespace] = max(500, 2 * len(store))
            except (OSError, TypeError) as exc:
                logger.warning("cache: failed to persist %s: %s", key, exc)
