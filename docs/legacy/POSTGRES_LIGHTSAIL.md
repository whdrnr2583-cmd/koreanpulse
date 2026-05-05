# Postgres + Lightsail webhook (superseded 2026-05-05)

> **Status: superseded.** As of 2026-05-05 the billing path moved to a
> Cloudflare Worker + D1 (SQLite) deployment in [`webhook-worker/`](../../webhook-worker/README.md).
> Operators should not stand up new Lightsail boxes or Postgres instances
> for koreanpulse billing — start fresh on D1 instead.
>
> This file is retained as historical reference only. The Python
> `koreanpulse-webhook` FastAPI app + `koreanpulse.license_postgres`
> module remain in the source tree for back-compat but are not used in
> the supported deployment path.

The original architecture (pre-2026-05-05) used:

- **Lightsail** ($5/mo) Ubuntu instance with SSH + systemd + Caddy.
- **Postgres 14+** (Supabase free tier or Render $7/mo) for the
  `LicenseStore`, with schema in `migrations/001_licenses.sql`.
- **`koreanpulse-webhook` console script** — FastAPI app, separate
  process from the MCP server, accepting Lemon Squeezy POST webhooks
  on `:8788` behind Caddy.

If you must read the original write-up to understand a legacy deploy,
consult repo history before commit `<TBD: tag the cutover commit>`.

## Why this was retired

- Lightsail box + Postgres = ~$5–12/mo + ops surface (SSH, systemd,
  Caddy, env-file management, backup discipline).
- D1 + Worker = $0 + zero ops, single Cloudflare dashboard alongside
  the cache-worker and daily-worker.
- Free-tier headroom on D1 is several orders of magnitude past the
  expected paid traffic at $5K MRR scale.

## Migration path

For anyone running the old Lightsail/Postgres deployment with live
licenses:

```bash
# 1. Dump from Postgres
psql $DATABASE_URL -c "\COPY (SELECT key, plan, customer_email, active,
                              created_at, period_calls, period_started_at,
                              metadata::text FROM licenses) TO 'licenses.csv' CSV HEADER"

# 2. Import to D1 (small script or hand-edit if <100 rows).
# 3. Tear down the Lightsail box and Postgres.
```

For v0 (zero production traffic yet at the time of cutover), this was a
non-issue — operators started fresh on D1.

## What still works in the source tree

The Python source still ships these modules for grandfathered users:

- `koreanpulse.billing.webhook_app` — FastAPI app
- `koreanpulse.license_postgres.PostgresLicenseStore` — async Postgres
  store
- `koreanpulse-webhook` console script
- `migrations/001_licenses.sql` — Postgres schema

None of these are referenced from the supported customer-facing setup
docs anymore. The current path is `webhook-worker/` (Cloudflare Worker
+ D1).
