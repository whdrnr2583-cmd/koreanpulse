# koreanpulse-webhook

Cloudflare Worker that handles **Polar** billing webhooks and license
validation, backed by Cloudflare D1 (SQLite). Polar is our sole billing
provider, active since 2026-05-06. The Lemon Squeezy store application
was declined the same day and LS is **not in use** — its handler code
remains in the repo only as a historical implementation reference. No
LS variant secrets are configured in production and none should be.
Replaces the older Lightsail FastAPI deployment.

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
POST /webhook/polar                     ← active provider
  Standard Webhooks signature verify
    (POLAR_WEBHOOK_SECRET, headers webhook-id / -timestamp / -signature)
  → JSON parse
  → idempotency check (D1 webhook_events PK on webhook-id)
  → dispatch on type
       subscription.created / .active / .updated / .canceled / .revoked
  → resolve product_id → plan via POLAR_PRODUCT_SOLO/_ANALYST/_DESK
  → upsert D1 licenses (metadata.provider = "polar")
  → email license key via Resend on subscription.created
  → audit row in webhook_events
  → 200 (always, unless infra error)

POST /webhook/lemonsqueezy              ← not in use; LS rejected 2026-05-06
  HMAC-SHA256 verify (LEMONSQUEEZY_WEBHOOK_SECRET)
  Handler code retained only as a historical implementation reference.
  No LS variant secrets are configured in production, so any incoming
  event resolves to "unknown plan" and the response is a graceful no-op
  rather than a 500. Do not configure LS secrets — Polar is our sole
  MoR and any LS traffic in production is by definition spurious.

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
| Workers requests | ~100 (Polar webhook on each sale + validate every 60s/license) | 100K/day | 1000× |
| D1 reads | ~50 (per validate hit on first) | 5M/day | 100K× |
| D1 writes | ~5 (Polar event + license issue) | 100K/day | 20K× |

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

# 3. Set secrets — Polar is the active provider (2026-05-06+)
npx wrangler secret put POLAR_WEBHOOK_SECRET            # `polar_whs_…` from the Polar webhook page
npx wrangler secret put POLAR_API_TOKEN                 # `polar_oat_…` (subscriptions:read scope)
npx wrangler secret put POLAR_PRODUCT_SOLO              # UUID of Cloud Solo product
npx wrangler secret put POLAR_PRODUCT_ANALYST           # UUID of Cloud Analyst product
npx wrangler secret put POLAR_PRODUCT_DESK              # UUID of Cloud Desk product
npx wrangler secret put RESEND_API_KEY                  # for license-key email on subscription.created
npx wrangler secret put KOREANPULSE_CACHE_SHARED_SECRET # same value cache-worker uses

# Lemon Squeezy — not in use. Their store application was declined
# 2026-05-06 and Polar is our sole billing provider. Do NOT set any
# LEMONSQUEEZY_* secret in production. The slots below are documented
# only because the handler code is still in the repo as a historical
# implementation reference; setting them would attempt to dispatch
# licenses against a provider with no current MoR relationship.
#   npx wrangler secret put LEMONSQUEEZY_WEBHOOK_SECRET
#   npx wrangler secret put LEMONSQUEEZY_VARIANT_SOLO         # Cloud Solo $29/mo
#   npx wrangler secret put LEMONSQUEEZY_VARIANT_ANALYST      # Cloud Analyst $79/mo
#   npx wrangler secret put LEMONSQUEEZY_VARIANT_DESK         # Cloud Desk $249/mo
#   npx wrangler secret put LEMONSQUEEZY_VARIANT_LIFETIME     # Design Partner $299
# Deprecated/legacy slots (only kept so a pre-2026-05-05 storefront
# would not 500): LEMONSQUEEZY_VARIANT_PRO / _STARTER / _INDIE / _ENTERPRISE.

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

In Polar dashboard:
1. Settings → Webhooks → Add endpoint
2. URL: `https://api.koreanpulse.dev/webhook/polar`
   (or `https://koreanpulse-webhook.<account>.workers.dev/webhook/polar`
   if no custom domain yet)
3. Events: `subscription.created` / `subscription.active` /
   `subscription.updated` / `subscription.canceled` / `subscription.revoked`
4. Signing secret: copy into `POLAR_WEBHOOK_SECRET` via `wrangler secret put`
5. Product UUIDs (Solo / Analyst / Desk): copy into
   `POLAR_PRODUCT_SOLO` / `POLAR_PRODUCT_ANALYST` / `POLAR_PRODUCT_DESK`

The Lemon Squeezy dashboard configuration is **not** part of the deploy
path. LS is not in use (store application declined 2026-05-06) and we
do not plan to re-apply.

## Custom domain

Cloudflare dashboard → Workers → koreanpulse-webhook → Triggers → Custom Domain
- `api.koreanpulse.dev` → koreanpulse-webhook

## Querying D1 (ops debugging)

```bash
# How many active licenses?
npx wrangler d1 execute koreanpulse_db --remote \
  --command "SELECT COUNT(*) FROM licenses WHERE active = 1"

# Per-plan / per-active breakdown
npx wrangler d1 execute koreanpulse_db --remote --json \
  --command "SELECT plan, active, COUNT(*) AS cnt
             FROM licenses
             GROUP BY plan, active
             ORDER BY cnt DESC"

# Audience composition (the BETA.md decision-matrix query)
npx wrangler d1 execute koreanpulse_db --remote --json \
  --command "SELECT json_extract(metadata, '$.self_description') AS role,
                    COUNT(*) AS n
             FROM licenses
             GROUP BY role
             ORDER BY n DESC"

# Provider attribution (Polar vs the dormant LS path)
npx wrangler d1 execute koreanpulse_db --remote --json \
  --command "SELECT json_extract(metadata, '$.provider') AS provider,
                    COUNT(*) AS n
             FROM licenses
             GROUP BY provider"

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
- `licenses` — one row per issued license. Carries `metadata.provider`
  (`"polar"` or, historically, `"lemonsqueezy"`) so source attribution
  is per-row. Denormalised `is_lifetime` + `deal_seq` columns to keep
  lifetime accounting fast.
- `webhook_events` — idempotency log. PK on `webhook_id` makes duplicate
  inserts fail with UNIQUE constraint, which the handler treats as
  "already processed."

## Pricing v2 (2026-05-05)

Production exercises three Polar products: Cloud Solo $29/mo, Cloud
Analyst $79/mo, Cloud Desk $249/mo. The plan CHECK constraint still
allows deprecated values (`free` / `starter` / `indie` / `pro` /
`enterprise`) so any pre-pricing-v2 license row continues to resolve.
New purchases go to `solo` / `analyst` / `desk`.

The Lemon Squeezy variant slots (`LEMONSQUEEZY_VARIANT_SOLO/_ANALYST/_DESK/_LIFETIME`
plus the deprecated `_PRO` / `_STARTER` / `_INDIE` / `_ENTERPRISE`)
remain wired in code only as a historical implementation reference. LS
is not in use (store application declined 2026-05-06) and the slots
are intentionally **unset in production**; any LS webhook delivery
resolves to "unknown plan" → no-op.

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

- Polar webhook: Standard Webhooks signature, HMAC-SHA256 over
  `webhook-id.webhook-timestamp.body`, constant-time compare.
- LS webhook (not in use): HMAC-SHA256 (constant-time compare) — same
  guarantee, retained only as a historical implementation reference.
- Both endpoints reject on signature mismatch.
- Secrets via `wrangler secret put` — never in `wrangler.toml`.
- License keys are 32 random bytes (urlsafe-base64), `kp_` prefix.
- License key never logged in full (Worker `console.warn` follows the
  Python convention of `key.slice(0,8)+"…"`).
- D1 auto-encrypted at rest by Cloudflare.
- Idempotency log retains webhook IDs indefinitely (no PII inside —
  only the provider event identifier).

## Legal posture

License store contains email addresses (PII). Cloudflare D1 is
GDPR-compliant storage. **Polar Software Inc. is the sole Merchant of
Record** — they collect and remit VAT / sales tax / GST and handle KYC,
refunds, and chargebacks for all sales. We have no MoR relationship
with Lemon Squeezy (their store application was declined 2026-05-06).
