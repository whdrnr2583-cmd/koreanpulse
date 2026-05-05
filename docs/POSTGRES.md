# Postgres-backed LicenseStore — production setup

In-memory store is fine for local dev (resets on restart). For real customers
you want persistence + indexed lookups + multi-process safety. That's Postgres.

## What you need

- A Postgres 14+ database. Recommended:
  - **Supabase** free tier (500MB, plenty for any indie scale)
  - Neon free tier
  - Render Postgres ($7/mo)
  - RDS / self-hosted, etc.
- DSN string of the form `postgresql://user:pw@host:port/db?sslmode=require`

## Steps

### 1. Apply the schema (once)

```bash
psql "$DATABASE_URL" -f migrations/001_licenses.sql
```

The migration is idempotent (`CREATE TABLE IF NOT EXISTS`, etc.) so safe to
rerun if you change envs.

For Supabase: **SQL Editor → New query → paste contents of
`migrations/001_licenses.sql` → Run**.

### 2. Install the optional extra

```bash
pip install 'koreanpulse[postgres]'
```

This adds `asyncpg`. The base install stays lean — Postgres is opt-in.

### 3. Wire the store at startup

For the **webhook process** (`koreanpulse-webhook`):

```python
# koreanpulse_webhook_runner.py — replace the default app boot
import asyncio, os
from koreanpulse.license import set_default_store
from koreanpulse.license_postgres import PostgresLicenseStore
from koreanpulse.billing.webhook_app import _build_app
import uvicorn

async def setup() -> None:
    store = await PostgresLicenseStore.connect(os.environ["DATABASE_URL"])
    set_default_store(store)

asyncio.run(setup())
uvicorn.run(_build_app(), host="0.0.0.0", port=int(os.environ.get("PORT", 8788)))
```

Save as a file and run with `python koreanpulse_webhook_runner.py`.

For the **MCP server** (`koreanpulse`): same pattern. The server reads the
license store on every gated tool call — wire the same `PostgresLicenseStore`
in via `set_default_store()` before `mcp.run()`.

### 4. Verify

```python
import asyncio, os
from koreanpulse.license_postgres import PostgresLicenseStore

async def main():
    store = await PostgresLicenseStore.connect(os.environ["DATABASE_URL"])
    print("active licenses:", await store.count_active())
    print("next lifetime seq:", await store.next_lifetime_seq())
    await store.close()

asyncio.run(main())
```

Expected output for a fresh install: `active licenses: 0`, `next lifetime seq: 1`.

## Schema reference

```
licenses
├── id                  BIGSERIAL PK
├── key                 TEXT UNIQUE     -- the kp_… token shipped to customer
├── plan                TEXT (enum-checked: free/starter/indie/pro/enterprise)
├── customer_email      TEXT
├── active              BOOLEAN
├── created_at          TIMESTAMPTZ
├── period_calls        INTEGER         -- rolling counter, reset by webhook
├── period_started_at   TIMESTAMPTZ
├── metadata            JSONB           -- LS subscription_id, lifetime, deal_seq, ...
└── updated_at          TIMESTAMPTZ     -- auto via trigger
```

Indexes:
- `licenses_email_lower_idx` — case-insensitive email lookup (webhook hot path)
- `licenses_active_idx` — partial index for active-only queries
- `licenses_lifetime_idx` — partial index for lifetime-deal accounting

## Backups

For Supabase: free tier includes daily backups, 7-day retention. Plenty for v0.
For self-hosted: nightly `pg_dump` to S3 / Backblaze, even at $0.005/GB scale.

## Migrating from in-memory to Postgres without losing customers

In-memory state is lost on restart, so **migrate before you have any paying
customers**. If you somehow already have some:

1. Stop the in-memory webhook process (drains nothing important; LS retries).
2. Apply schema + start Postgres-backed webhook.
3. For each known customer, run a one-off insert from the LS dashboard data.

Set up Postgres before the first paid checkout. Don't skip this.
