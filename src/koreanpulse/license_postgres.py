"""Postgres-backed LicenseStore — production replacement for InMemoryLicenseStore.

Wires through asyncpg. Wire it up at process start:

    from koreanpulse.license import set_default_store
    from koreanpulse.license_postgres import PostgresLicenseStore

    store = await PostgresLicenseStore.connect(os.environ["DATABASE_URL"])
    set_default_store(store)

The same `LicenseStore` Protocol the webhook handler and MCP server already
use, just persistence-backed and indexed. Swap is one line.

Schema lives in `migrations/001_licenses.sql`. Apply once before first use:

    psql $DATABASE_URL -f migrations/001_licenses.sql
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from koreanpulse.license import (
    License,
    LicenseError,
    Plan,
)

if TYPE_CHECKING:
    import asyncpg  # noqa: F401

logger = logging.getLogger(__name__)


class PostgresLicenseStore:
    """LicenseStore backed by Postgres (asyncpg). Implements the same Protocol
    as InMemoryLicenseStore plus the email/lifetime helpers used by the
    Lemon Squeezy webhook handler.

    Construct via `await PostgresLicenseStore.connect(dsn)` — that does the
    pool setup. Don't instantiate directly.
    """

    def __init__(self, pool: "asyncpg.Pool") -> None:
        self._pool = pool

    # ── Construction ───────────────────────────────────────────────────────

    @classmethod
    async def connect(
        cls,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> "PostgresLicenseStore":
        """Open a pool and return a ready store.

        DSN forms accepted by asyncpg: `postgres://user:pw@host:port/db` or
        `postgresql://...` plus `?sslmode=require` for managed services.
        """
        try:
            import asyncpg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "asyncpg not installed. Run: pip install 'koreanpulse[postgres]'"
            ) from exc

        pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    # ── LicenseStore Protocol ─────────────────────────────────────────────

    async def get(self, key: str) -> Optional[License]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM licenses WHERE key = $1", key
            )
        return _row_to_license(row) if row else None

    async def save(self, lic: License) -> None:
        """Upsert by key. Lets the same License object round-trip cleanly."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO licenses (
                    key, plan, customer_email, active, created_at,
                    period_calls, period_started_at, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                ON CONFLICT (key) DO UPDATE SET
                    plan              = EXCLUDED.plan,
                    customer_email    = EXCLUDED.customer_email,
                    active            = EXCLUDED.active,
                    period_calls      = EXCLUDED.period_calls,
                    period_started_at = EXCLUDED.period_started_at,
                    metadata          = EXCLUDED.metadata
                """,
                lic.key,
                lic.plan.value,
                lic.customer_email,
                lic.active,
                lic.created_at,
                lic.period_calls,
                lic.period_started_at,
                json.dumps(lic.metadata, ensure_ascii=False, default=str),
            )

    async def increment_usage(self, key: str, n: int = 1) -> int:
        """Atomic counter bump. Raises LicenseError if key not found."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE licenses
                   SET period_calls = period_calls + $2
                 WHERE key = $1
                RETURNING period_calls
                """,
                key, n,
            )
        if row is None:
            raise LicenseError("invalid", f"license key not found: {key[:8]}…")
        return int(row["period_calls"])

    # ── Lemon Squeezy webhook helpers ─────────────────────────────────────

    async def find_by_email(self, email: str) -> Optional[License]:
        """Indexed lookup. Returns the most recently created license for the
        email (case-insensitive)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM licenses
                 WHERE LOWER(customer_email) = LOWER($1)
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                email,
            )
        return _row_to_license(row) if row else None

    async def next_lifetime_seq(self) -> int:
        """Next 1-indexed deal_seq for a new lifetime license."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COALESCE(MAX((metadata->>'deal_seq')::INTEGER), 0) AS max_seq
                  FROM licenses
                 WHERE metadata->>'lifetime' = 'true'
                """
            )
        return int(row["max_seq"]) + 1

    async def count_active(self) -> int:
        """Cheap dashboard helper."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM licenses WHERE active = TRUE"
            )
        return int(row["n"])


# ── Helpers ────────────────────────────────────────────────────────────────


def _row_to_license(row) -> License:  # asyncpg.Record
    metadata_raw = row["metadata"]
    if isinstance(metadata_raw, str):
        metadata = json.loads(metadata_raw)
    elif isinstance(metadata_raw, dict):
        metadata = metadata_raw
    else:
        metadata = {}

    return License(
        key=row["key"],
        plan=Plan(row["plan"]),
        customer_email=row["customer_email"],
        active=row["active"],
        created_at=_as_datetime(row["created_at"]),
        period_calls=int(row["period_calls"]),
        period_started_at=_as_datetime(row["period_started_at"]),
        metadata=metadata,
    )


def _as_datetime(value) -> datetime:
    """asyncpg returns timezone-aware datetime already; just re-type for safety."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
