# koreanpulse-daily

Cloudflare Worker that builds the **`koreanpulse.dev/today`** daily Korean
equity dashboard — DART activist filings + key disclosures, summarised in
English, refreshed once per market close.

This is the **traffic / retention surface** of koreanpulse. The MCP server
(`src/koreanpulse/`) targets agents; this Worker targets human readers
showing up daily on a phone or laptop. Same data, different form.

## What it does

```
KST 16:30 cron (1×/weekday)
  ├─ Pull DART type-D filings (last 7d) → match against Korean activist allowlist
  ├─ Pull DART type-A/B filings (last 1d) → top 10 by recency
  ├─ Translate titles + summarise activist filings via OpenAI gpt-5-mini
  ├─ Render HTML + JSON snapshot
  ├─ Write to KV (latest + per-date, 30-day history retention)
  └─ Push Discord webhook embed (if configured)

Visitor traffic
  ├─ GET /today        → KV → HTML, edge-cached 5 min
  ├─ GET /today.json   → KV → JSON, machine-readable
  ├─ GET /today/:date  → KV → HTML, history (last 30 days)
  └─ GET /health       → liveness probe
```

## Free-tier budget

| Service | Daily usage | Free tier limit | Headroom |
|---|---|---|---|
| Workers requests | ~150 (1 cron + visitors) | 100,000/day | 666× |
| KV writes | ~5 (HTML+JSON, latest+date, snapshot) | 1,000/day | 200× |
| KV reads | 1× per visitor | 100,000/day | 666× (at 150 visitors) |
| Cron triggers | 1× | unmetered | — |
| OpenAI cost | ~5 fresh calls × $0.001 | — | ≈ $0.15/month |
| DART calls | ~3 (1 type-D + 2 type-A/B) | 32,000 soft cap | 0.01% |

→ Production deploys to Cloudflare's free tier indefinitely until traffic
crosses ~5,000 visitors/day. By then we're either monetising or pivoting.

## Local dev

```bash
cd daily-worker
npm install
# One-time KV namespace
npx wrangler kv:namespace create DAILY
npx wrangler kv:namespace create DAILY --preview
# Paste both IDs into wrangler.toml.

# Secrets
npx wrangler secret put DART_API_KEY        # 40K/day; reuse the koreanpulse key
npx wrangler secret put OPENAI_API_KEY      # gpt-5-mini-capable key
npx wrangler secret put DISCORD_WEBHOOK_URL # optional; channel webhook URL

npm run dev                 # http://localhost:8787
# Force-trigger the scheduled handler locally:
npm run build-once
```

## Deploy

```bash
npx wrangler deploy
# Then in Cloudflare dashboard → Workers → Triggers:
#   1. add custom domain `koreanpulse.dev` (or a subdomain like `daily.koreanpulse.dev`)
#   2. confirm the cron trigger `30 7 * * 1-5` is active
```

## Manual rebuild (ops)

If the cron failed or you want to rebuild after a code change without
waiting for the next 16:30 KST:

```bash
curl -H "x-admin-key: $DART_API_KEY" https://koreanpulse.dev/admin/rebuild
```

(The shared admin key is reused — knowing the DART key implies operator
status.) Returns `{ ok: true, activists: N, top: M, date: "..." }`.

## Architecture notes

- **No backend dependency**. The Worker talks directly to DART + OpenAI.
  No round-trip to the Lightsail webhook server, no Postgres read.
- **No license check**. `/today` is the free-tier funnel front door; the
  `koreanpulse-cache` Worker is where licensing lives. Premium retention
  (Discord push priority, history depth, search) gets layered later.
- **No client-side JS**. Tailwind via CDN, plain HTML. Page weight < 30 KB.
  Cloudflare edge caches the HTML — visitors land on instant first paint.
- **KV as cache-of-truth**. The Worker never re-fetches DART on a visitor
  request; it only re-fetches on the cron tick. This is what keeps DART
  quota usage in single digits per day regardless of traffic.

## Legal posture (mirrors `koreanpulse` proper)

- **DART**: public, free redistribution with attribution. ✅
- **Korean broker reports**: not included.
- **Korean news**: not included on `/today` v0; if added later, fair-use
  summary + outbound link only, never full-text.
- **Investment advice**: none. All summaries are factual extraction.
