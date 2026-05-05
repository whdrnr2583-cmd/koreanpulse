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
entries get filtered on read; the on-disk line stays until next compaction.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

    Expired entries stay on disk until a future compaction step (not yet
    implemented; .jsonl files are append-only). For our scale this is fine
    for many months before disk noise matters.

    Thread-safe within a single asyncio loop via an asyncio.Lock per instance.
    """

    def __init__(self, root: str | Path = ".data/cache") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        # store[namespace][key] = {"v": value, "exp": float|None}
        self._stores: dict[str, dict[str, dict[str, Any]]] = {}
        self._loaded: set[str] = set()
        self._lock = asyncio.Lock()

    def _path(self, namespace: str) -> Path:
        return self._root / f"{namespace}.jsonl"

    def _ensure_loaded(self, namespace: str) -> dict[str, dict[str, Any]]:
        if namespace in self._loaded:
            return self._stores.setdefault(namespace, {})
        store: dict[str, dict[str, Any]] = {}
        path = self._path(namespace)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
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
        self._stores[namespace] = store
        self._loaded.add(namespace)
        return store

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
            except (OSError, TypeError) as exc:
                logger.warning("cache: failed to persist %s: %s", key, exc)
