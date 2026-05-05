"""Tests for PostgresLicenseStore.

Skipped automatically if DATABASE_URL_TEST is not set — keeps CI green when
no test DB is available. To run:

    DATABASE_URL_TEST=postgres://localhost/koreanpulse_test pytest tests/test_license_postgres.py
"""
from __future__ import annotations

import os

import pytest

# Skip the whole module if asyncpg or test DB env is missing.
asyncpg = pytest.importorskip("asyncpg")

DATABASE_URL_TEST = os.environ.get("DATABASE_URL_TEST", "").strip()
pytestmark = pytest.mark.skipif(
    not DATABASE_URL_TEST,
    reason="DATABASE_URL_TEST not set; skipping PostgresLicenseStore live tests",
)

from koreanpulse.license import (  # noqa: E402
    License,
    LicenseError,
    Plan,
    issue_license_key,
)
from koreanpulse.license_postgres import PostgresLicenseStore  # noqa: E402


SCHEMA_SQL = open(
    os.path.join(os.path.dirname(__file__), "..", "migrations", "001_licenses.sql"),
    encoding="utf-8",
).read()


@pytest.fixture
async def store():
    """Fresh schema for each test (TRUNCATE between)."""
    pool = await asyncpg.create_pool(DATABASE_URL_TEST)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        await conn.execute("TRUNCATE TABLE licenses RESTART IDENTITY")
    s = PostgresLicenseStore(pool)
    yield s
    await s.close()


def make_license(plan: Plan = Plan.INDIE, email: str = "t@example.com") -> License:
    return License(key=issue_license_key(), plan=plan, customer_email=email)


class TestSaveAndGet:
    @pytest.mark.asyncio
    async def test_roundtrip(self, store):
        lic = make_license()
        await store.save(lic)
        got = await store.get(lic.key)
        assert got is not None
        assert got.key == lic.key
        assert got.plan == lic.plan
        assert got.customer_email == lic.customer_email
        assert got.active is True

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        assert await store.get("kp_doesnotexist") is None

    @pytest.mark.asyncio
    async def test_save_upsert(self, store):
        lic = make_license(Plan.STARTER)
        await store.save(lic)
        # Mutate and save again
        lic.plan = Plan.PRO
        lic.active = False
        await store.save(lic)
        got = await store.get(lic.key)
        assert got.plan == Plan.PRO
        assert got.active is False


class TestIncrementUsage:
    @pytest.mark.asyncio
    async def test_increment(self, store):
        lic = make_license()
        await store.save(lic)
        n = await store.increment_usage(lic.key, n=5)
        assert n == 5
        n = await store.increment_usage(lic.key, n=3)
        assert n == 8

    @pytest.mark.asyncio
    async def test_increment_nonexistent_raises(self, store):
        with pytest.raises(LicenseError) as ei:
            await store.increment_usage("kp_nope")
        assert ei.value.code == "invalid"


class TestEmailLookup:
    @pytest.mark.asyncio
    async def test_find_by_email_case_insensitive(self, store):
        lic = make_license(email="Alice@Example.com")
        await store.save(lic)
        got = await store.find_by_email("alice@example.com")
        assert got is not None
        assert got.key == lic.key

    @pytest.mark.asyncio
    async def test_find_returns_most_recent(self, store):
        for plan in (Plan.STARTER, Plan.INDIE, Plan.PRO):
            lic = make_license(plan=plan, email="dup@x.com")
            await store.save(lic)
        got = await store.find_by_email("dup@x.com")
        assert got.plan == Plan.PRO  # last inserted

    @pytest.mark.asyncio
    async def test_find_no_match(self, store):
        assert await store.find_by_email("ghost@nowhere.com") is None


class TestLifetimeSeq:
    @pytest.mark.asyncio
    async def test_first_seq_is_one(self, store):
        assert await store.next_lifetime_seq() == 1

    @pytest.mark.asyncio
    async def test_seq_increments(self, store):
        for i in range(1, 4):
            lic = make_license(email=f"life{i}@x.com")
            lic.metadata = {"lifetime": True, "deal_seq": i}
            await store.save(lic)
        assert await store.next_lifetime_seq() == 4

    @pytest.mark.asyncio
    async def test_non_lifetime_ignored(self, store):
        # A non-lifetime license shouldn't affect the counter
        lic = make_license()
        await store.save(lic)
        assert await store.next_lifetime_seq() == 1


class TestCountActive:
    @pytest.mark.asyncio
    async def test_count(self, store):
        a = make_license()
        b = make_license(email="b@x.com")
        c = make_license(email="c@x.com")
        c.active = False
        for lic in (a, b, c):
            await store.save(lic)
        assert await store.count_active() == 2
