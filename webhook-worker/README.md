# koreanpulse-webhook

Cloudflare Worker that handles Lemon Squeezy billing webhooks and license
validation, backed by Cloudflare D1 (SQLite). Replaces the Lightsail
FastAPI deployment.

## Why this exists

The Python `koreanpulse-webhook` (FastAPI on Lightsail + Postgres) was
fine but added an entire AWS box and a Postgres install to the operator's
plate. The simplification path is to fold all three workers + D1 onto
Cloudflare, free tier, single dashboard.

```
Lightsail FastAPI + Postgres   →   Cloudflare Worker + D1
~$5/mo + ops                   →   $0 + zero ops
SSH + systemd + Caddy          →   `wrangler deploy`
```

## What it does

```
POST /webhook/lemonsqueezy
  HMAC-SHA256 verify (LEMONSQUEEZY_WEBHOOK_SECRET)
  → JSON parse
  → idempotency check (D1 webhook_events PK)
  → dispatch on meta.event_name
       subscription_created/_resumed/_updated/_cancelled/_expired
       subscription_payment_success/_failed
       order_created  (lifetime SKU)
  → upsert D1 licenses
  → audit row in webhook_events
  → 200 (always, unless infra error)

POST /v1/validate
  HMAC verify (KOREANPULSE_CACHE_SHARED_SECRET, shared with cache-worker)
  → JSON parse
  → D1 SELECT licenses WHERE key = ?
  → check active + monthly quota
  → atomic UPDATE period_calls + 1
  → 200 with { ok, plan, period_calls }

GET /health
  → { "status": "ok" }
```

## Free-tier budget

| Service | Daily usage | Free limit | Headroom |
|---|---|---|---|
| Workers requests | ~100 (LS webhook on each sale + validate every 60s/license) | 100K/day | 1000× |
| D1 reads | ~50 (per validate hit on first) | 5M/day | 100K× |
| D1 writes | ~5 (LS event + license issue) | 100K/day | 20K× |

Several orders of magnitude headroom even at $5K MRR scale.

## Local dev

```bash
cd webhook-worker
npm install

# 1. Create the D1 database (one-time, both local and remote envs)
npx wrangler d1 create koreanpulse_db
# Paste the returned database_id into wrangler.toml.

# 2. Apply schema
npm run migrate:local      # local SQLite for `npm run dev`
npm run migrate:prod       # remote D1 for production

# 3. Set secrets — pricing v2 (2026-05-05+)
npx wrangler secret put LEMONSQUEEZY_WEBHOOK_SECRET
npx wrangler secret put KOREANPULSE_CACHE_SHARED_SECRET   # same as cache-worker

# Active pricing v2 variants — one per published tier
npx wrangler secret put LEMONSQUEEZY_VARIANT_SOLO         # Cloud Solo $29/mo
npx wrangler secret put LEMONSQUEEZY_VARIANT_ANALYST      # Cloud Analyst $79/mo
npx wrangler secret put LEMONSQUEEZY_VARIANT_DESK         # Cloud Desk $249/mo
npx wrangler secret put LEMONSQUEEZY_VARIANT_LIFETIME     # Design Partner $299 (private)

# Deprecated / back-compat — leave unset in production:
#   LEMONSQUEEZY_VARIANT_PRO / _STARTER / _INDIE / _ENTERPRISE
# These are kept only so historical webhook payloads from a pre-2026-05-05
# storefront still resolve to a known plan instead of 500ing.

# 4. Run locally
npm run dev      # http://localhost:8787

# 5. Smoke test
curl http://localhost:8787/health
# → {"status":"ok"}
```

## Deploy

```bash
npm run deploy
```

In Lemon Squeezy dashboard:
1. Settings → Webhooks → Add webhook
2. URL: `https://api.koreanpulse.dev/webhook/lemonsqueezy`
   (or `https://koreanpulse-webhook.<account>.workers.dev/webhook/lemonsqueezy`
   if no custom domain yet)
3. Events: subscription_created / _updated / _cancelled / _payment_success / _payment_failed / order_created
4. Secret: same as `LEMONSQUEEZY_WEBHOOK_SECRET` you set

## Custom domain

Cloudflare dashboard → Workers → koreanpulse-webhook → Triggers → Custom Domain
- `api.koreanpulse.dev` → koreanpulse-webhook

## Querying D1 (ops debugging)

```bash
# How many active licenses?
npx wrangler d1 execute koreanpulse_db --remote \
  --command "SELECT COUNT(*) FROM licenses WHERE active = 1"

# Audience composition (the BETA.md decision-matrix query)
npx wrangler d1 execute koreanpulse_db --remote --json \
  --command "SELECT json_extract(metadata, '$.self_description') AS role,
                    COUNT(*) AS n
             FROM licenses
             GROUP BY role
             ORDER BY n DESC"

# Lifetime deal seats remaining
npx wrangler d1 execute koreanpulse_db --remote \
  --command "SELECT 100 - COUNT(*) AS remaining
             FROM licenses
             WHERE is_lifetime = 1"

# Recent webhook events
npx wrangler d1 execute koreanpulse_db --remote \
  --command "SELECT webhook_id, event_name, action, received_at
             FROM webhook_events
             ORDER BY received_at DESC
             LIMIT 20"
```

## Schema

- `migrations/0001_licenses.sql` — initial schema.
- `migrations/0002_pricing_v2.sql` — extends the `plan` CHECK constraint to
  permit `solo` / `analyst` / `desk` alongside the deprecated
  `free` / `starter` / `indie` / `pro` / `enterprise` strings.

Both files run via `npm run migrate:prod`.

Two tables:
- `licenses` — one row per issued license. Mirrors the Postgres schema
  in `migrations/001_licenses.sql` but with SQLite-compatible types
  (TEXT for timestamps, INTEGER for booleans, JSON-as-TEXT for metadata).
  Denormalised `is_lifetime` + `deal_seq` columns to keep lifetime
  accounting fast without a JSON functional index.
- `webhook_events` — idempotency log. PK on `webhook_id` makes duplicate
  inserts fail with UNIQUE constraint, which the handler treats as
  "already processed."

## Pricing v2 (2026-05-05)

Production exercises **`LEMONSQUEEZY_VARIANT_SOLO`,
`LEMONSQUEEZY_VARIANT_ANALYST`, `LEMONSQUEEZY_VARIANT_DESK`, and
`LEMONSQUEEZY_VARIANT_LIFETIME`** — the workflow-priced 3-tier ladder
plus the private design-partner one-time SKU. The plan CHECK constraint
still allows the deprecated values (`free` / `starter` / `indie` / `pro` /
`enterprise`) so any pre-pricing-v2 license row continues to resolve. New
purchases go to `solo` / `analyst` / `desk` (subscription) or `analyst` +
`is_lifetime=1` (one-time design-partner SKU).

The deprecated `LEMONSQUEEZY_VARIANT_PRO` / `_STARTER` / `_INDIE` /
`_ENTERPRISE` env slots remain wired up so an older storefront still
resolves to a known plan instead of returning a 500 — leave them unset
in production.

## Today vs Q3 2026

Today the worker enforces only `period_calls` against
`PLAN_CALLS_PER_MONTH`. The other tier dimensions (`watchlists`,
`alert_channels`, `seats`, `retention_days`) are configured in
`PLAN_LIMITS` but **not yet enforced at runtime** — they ship with the
watchlist polling loop and alert dispatch in Q3 2026.

## Migration from the old Lightsail webhook

If you have existing licenses in Postgres:

```bash
# 1. Dump from Postgres
psql $DATABASE_URL -c "\COPY (SELECT key, plan, customer_email, active,
                              created_at, period_calls, period_started_at,
                              metadata::text FROM licenses) TO 'licenses.csv' CSV HEADER"

# 2. Convert metadata JSONB → TEXT (already text in CSV) and import to D1
# Use a small script or hand-edit if <100 rows.
```

For v0 (no production traffic yet), this is a non-issue — start fresh on D1.

## Security model

- HMAC-SHA256 (constant-time compare) on both endpoints.
- Secrets via `wrangler secret put` — never in `wrangler.toml`.
- License keys are 32 random bytes (urlsafe-base64), `kp_` prefix.
- License key never logged in full (Worker `console.warn` follows the
  Python convention of `key.slice(0,8)+"…"`).
- D1 auto-encrypted at rest by Cloudflare.
- Idempotency log retains webhook IDs indefinitely (no PII inside —
  only the LS event identifier).

## Legal posture

License store contains email addresses (PII). Cloudflare D1 is GDPR-compliant
storage. Lemon Squeezy is the Merchant of Record so all sales tax /
KYC obligations route through them.
