<p align="center">
  <img src="docs/assets/logo.svg" alt="koreanpulse" width="256" height="256">
</p>

# koreanpulse

> Get pinged in English the moment a 5%-rule filing or DART event hits a stock you care about. **(Beta — watchlist polling + alert dispatch ship Q3 2026.)**

**The pitch**: We'll watch your KRX tickers in Korean and ping you in English when something material moves — foreign-holder 5%-rule disclosures, Korean activist filings, major DART events. KRX itself, ASIFMA, Wellington and Aberdeen all on record — Korean disclosure flow into English is structurally inadequate. Bloomberg costs $24K/yr and still misses the front page of 전자신문. We translate, classify, and route the same Korean primary sources institutional analysts read into your Discord / Telegram / inbox. Free public daily snapshot at `/today` (live today); paid Cloud tiers for the workflow (Solo $29/mo, Analyst $79/mo, Desk $249/mo) — **lock-in pricing for waitlist; queries + hosted translation are live today, watchlist polling + alert dispatch ship Q3 2026**. OSS self-host available for hackers — see [Run it yourself](#run-it-yourself-oss).

---

## Status

**Pre-alpha (v0.0.0).** 7 MCP tools shipped. 181 tests pass. Beta/waitlist tone — watchlist polling + alert dispatch ship Q3 2026. Beta acquisition plan in `docs/BETA.md`.

---

## Why this exists

> "Majority of foreign investors find it surprisingly difficult to penetrate the Korean hedge fund market due to its limited accessibility and availability of information in foreign language." — *HedgeVista, 2025*

> "Published information should be made available in both Korean and English for all investors." — *ASIFMA Korean Capital Markets Report, 2022*

> "The Korea Exchange will provide investor relations services to companies that lack the capability, particularly in English." — *Wellington Management on Korea Value-Up program, 2025*

The English-IR gap is multi-source verified. The triggers below sit on top of it:

- **2026-04 to 05 retail inflection** — Hana × Futu (3.3M HK retail accounts) and Samsung × Interactive Brokers (4.6M global retail) launched direct KRX trading in the **last 7 days**. ~7.9M foreign retail accounts now wired in, up from ~0 two years ago. May 4 saw a record 3.9T₩ ($2.7B) single-day foreign net-buy on KOSPI+NXT. (Sources: FSC, 주간한국, KED Global)
- KOSPI on the **MSCI Developed Market** watchlist → expected foreign capital inflow
- IRC (Investor Registration Certificate) abolished Dec 2023 — foreign account openings accelerated 3–4× vs 2023 baseline (FSC)
- Millennium made its first Korean allocation ($250M to Billionfold) in 2025
- Korean activist scene maturing (KCGI, Align Partners) + global activists filing in Korea (ValueAct, Elliott)
- Korean shipbuilding, HBM, defense, biotech all globally relevant — but Korean-only sourcing
- Korean retail rotated heavily out of crypto into KOSPI ($110B left Upbit/Bithumb in 2025)
- Bloomberg/FactSet enterprise tier only — **indie/SMB tier empty**

## Who pays

| Audience | Plan | Why |
|---|---|---|
| Crypto-native rotator into KOSPI/KOSDAQ | Cloud Solo $29/mo | One Discord channel pinged on watchlist hits — that's the whole job |
| Korean diaspora / overseas Korean investor | Cloud Solo $29/mo | English digest of the news they grew up reading, alerts to Telegram |
| K-content / EM journalist | Cloud Solo $29/mo | Replaces hours of manual translation, daily English digest |
| Boutique fund analyst covering Korea | Cloud Analyst $79/mo | 25 watchlists, 1-year archive search, multiple alert channels, CSV/JSON export |
| Paid-research-budget retail trader | Cloud Analyst $79/mo | Saved searches, priority cache, multi-channel alerts |
| Boutique long/short desk, small research team | Cloud Desk $249/mo | 3 seats, shared watchlists, Slack/webhook alerts, team archive |

The free daily snapshot at [`/today`](https://koreanpulse.dev/today) (no login, no API key) is the funnel front door — a preview of the daily digest paying customers get pushed to their channel of choice.

> _Design partner program available for the first 20 named seats — contact us._

## Pricing

> 🚧 **Beta — lock-in pricing for waitlist.** Solo $29 / Analyst $79 / Desk $249. Queries + hosted translation cache are live today. Watchlist polling, alert dispatch, seat enforcement, and per-tier retention windows ship Q3 2026. Today the **only runtime-enforced difference** between tiers is the **monthly query cap (2K / 15K / 100K)**; seat counts, watchlist counts, alert-channel limits, and archive-retention windows are paper limits until the polling/dispatch loop lands. Early supporters keep the launch rate — no auto-charge until the workflow ships.

| Tier | $/mo | Watchlists | Queries/mo | Archive | Alert channels |
|---|---|---|---|---|---|
| **Cloud Solo** | **29** | 5 *(Q3 2026)* | ~2,000 *(live)* | 30 days *(Q3 2026)* | 1 Discord or Telegram *(Q3 2026)* |
| **Cloud Analyst** | **79** | 25 *(Q3 2026)* | ~15,000 *(live)* | 1 year *(Q3 2026)* | Multi (Discord / Telegram / Email) *(Q3 2026)* |
| **Cloud Desk** | **249** | shared, 3 seats *(Q3 2026)* | ~100,000 *(live)* | team archive *(Q3 2026)* | Slack / webhooks *(Q3 2026)* |

Annual billing: **−20%** at launch. 30-day refund.

> **Enterprise / SLA**: contact us. No published price.

## Run it yourself (OSS)

Source is AGPL-3.0. Self-hosters can run the MCP server locally with their own DART and OpenAI keys. This path is for hackers and max-privacy users.

| | OSS self-host | Cloud (Solo / Analyst / Desk) |
|---|---|---|
| Cost | $0 | $29 / $79 / $249 per month |
| Provider keys | your `DART_API_KEY` + your `OPENAI_API_KEY` | your `DART_API_KEY` (stays local); we hold the OpenAI key for you |
| Local install required | yes (`pip install koreanpulse`) | yes (same `pip install`; only translation calls hit our Worker) |
| Watchlist polling + alerts | not included | **Q3 2026 ship target** (waitlist) |
| Hosted archive | none | **Q3 2026 ship target** (30 days / 1 year / team archive) |
| Hosted translation cache | none | included (cross-tenant cache hits compound, live today) |
| Account sync | none | **Q3 2026 ship target** |
| Support | community only (issues/PRs) | priority support on Analyst / Desk |
| Best for | hackers, privacy-strict envs, OSS contributors | anyone who'll want the watchlist-to-alert workflow once it ships |

OSS self-host is **not** in the pricing table above — it's a separate lane. See [`docs/SELF_HOSTING.md`](docs/SELF_HOSTING.md) for the install + key wiring. A true HTTP-transport remote MCP (no local install at all) is on the roadmap but not yet shipped.

## What it does

7 MCP tools shipped, callable from Claude Desktop / Cursor / any MCP client:

| Tool | One-line |
|---|---|
| `track_korean_filings` | DART filings real-time + EN translation/summary |
| `monitor_activist_investors` | Activist 5%-rule filings auto-tagged (KCGI / Align / Truston / Anda / Cha / VIP / ValueAct / Elliott) |
| `monitor_foreign_holders` | Foreign 5%-rule disclosures (BlackRock / Vanguard / Norges / GIC / Temasek + 15 more) |
| `lookup_corp_code` | Korean company name → DART corp code |
| `resolve_stock_code` | KRX 6-digit → DART corp entry |
| `search_korean_industry_news` | etnews / 한국경제 RSS, classified into 16 industries |
| `koreanpulse_about` | Server info / available tools |

5 more planned (`docs/SPEC.md`): `digest_analyst_reports`, `monitor_activist_investors`, `get_ma_pipeline`, `track_government_policy`, `summarize_korean_earnings_call`.

## Differentiation vs incumbents

| | Bloomberg | FactSet | KED Global | **koreanpulse** |
|---|---|---|---|---|
| Korean primary source depth | medium | medium | English wire only | **deep** |
| Real-time AI agent integration (MCP) | none | none | none | **native** |
| Indie/SMB pricing | none ($24K+/yr) | none | free (low signal) | **$29 / $79 / $249 Cloud tiers (waitlist, lock-in)** |
| Korean activist / M&A pipeline | weak | weak | reactive | **proactive watch** *(Q3 2026)* |

## Capacity (DART quota math)

DART caps each API key at **40,000 calls/day** (verified 2026-05). We enforce a soft cap at **32,000/day (80%)** with `DART_DAILY_QUOTA` env override.

Filing-list responses go through `list_filings_cached()` with a freshness-aware TTL (60s for today's window, 1h for ≤6d old, 24h for ≥7d old). Cache hits don't burn DART quota.

| Cache hit | Customer ceiling/day | MAU ceiling (12mo mix) |
|---|---|---|
| 0% (no filing cache) | 32,000 | ~800 |
| 70% (3-mo realistic) | 107,000 | **~9,500** |
| 85% (mature) | 213,000 | **~19,000** |
| 95% (high reuse) | ~25,000 MAU (DART-limited) | — |

Hard ceiling: **~30,000 MAU per DART key**. Second key (separate 사업자등록번호) required beyond that.

Forecast 12mo mix (756 MAU) sits at **~930 DART calls/day** = **2.9% of soft quota** with 70% cache. ~34× headroom to scale before quota engineering.

See `src/koreanpulse/cache.py`, `src/koreanpulse/dart.py:list_filings_cached`.

## Roadmap

**Live today**: queries (DART filings, foreign-holder + activist tracking, industry news), hosted translation cache (Cloud `KOREANPULSE_CACHE_MODE=hosted`), `/today` daily snapshot, Lemon Squeezy → D1 license issuance, **hosted HTTP-transport gateway via [Smithery](https://smithery.ai/servers/whdrnr2583/koreanpulse)** (no local install — clients connect at `koreanpulse--whdrnr2583.run.tools`).

**Q3 2026 ship targets** (waitlist):
- Watchlist polling loop (Cloudflare cron + `koreanpulse.alerts`)
- Alert dispatch enforcement (Discord / Telegram / Slack / webhook)
- Per-tier limit enforcement: watchlist count, alert-channel count, archive retention, seat count

**Earlier milestones**:
- **W1–2** ✅ project skeleton, FastMCP server, DART client, agentprod integration
- **W3–4** ✅ MVP: `track_korean_filings`, `lookup_corp_code`, `search_korean_industry_news`, translation layer with cache
- **W5–6** ✅ Lemon Squeezy webhook handler skeleton (license auto-issuance)
- **W5–6** ✅ Cloudflare D1-backed `LicenseStore` (replaces in-memory)
- **W7–8** ⏳ **Watchlist polling + alert dispatch** (Q3 2026 ship target) — wiring `cache-worker` cron + `daily-worker` cron + `koreanpulse.alerts` module into the watchlist-to-alert workflow that powers Solo / Analyst / Desk. D1 schema and alert-dispatch primitives already shipped; the cron loop is the missing piece.
- **W7–8** `digest_analyst_reports`, `summarize_korean_earnings_call`
- **W9–10** Multi-seat / shared watchlists for Cloud Desk
- **W11–12** First paid customer

## Architecture

- **MCP server** — FastMCP (Python), runs on the user's machine over stdio. Zero hosting cost on our side. Cloud customers still install this locally; switching `KOREANPULSE_CACHE_MODE=hosted` routes translation calls (only) to the Worker.
- **Cache Worker** ([`cache-worker/`](cache-worker/README.md)) — Cloudflare Workers + KV. Holds our OpenAI key, fronts a global translation cache, gates each call behind a license check. Free tier (100K req/day Workers + 100K read/day KV) covers paid traffic until well past $5K MRR.
- **Daily Worker** ([`daily-worker/`](daily-worker/README.md)) — Cloudflare Workers + KV. Cron-driven `/today` dashboard build (KST 16:30 weekdays).
- **Webhook Worker** ([`webhook-worker/`](webhook-worker/README.md)) — Cloudflare Worker + D1 (SQLite). Handles Lemon Squeezy events and `/v1/validate` for the Cache Worker. Replaces the old Lightsail/FastAPI/Postgres stack so the operator runs zero servers.
- **Reuses [`agentprod`](../agentprod)** — Throttle, Retry, CostTracker.

## OSS self-host vs Cloud

Two ways to run the MCP, switched via `KOREANPULSE_CACHE_MODE`. **Both require a local install** (`pip install koreanpulse` + 4-line Claude Desktop config); the difference is whether translation calls go through our Worker or directly to OpenAI from your machine.

| | `local` (OSS self-host) | `hosted` (Cloud Solo / Analyst / Desk) |
|---|---|---|
| Local MCP install | required | required (same `pip install`) |
| Provider key | your `OPENAI_API_KEY` | ours, on the Worker (no OpenAI key on your side) |
| Translation cache | local JSONL file | global Cloudflare KV (cross-tenant reuse) |
| Per-call cost | OpenAI billed to you | absorbed in your Cloud plan |
| Privacy | translation never leaves your machine + OpenAI | translation calls go to our Worker; DART traffic still local |
| Best for | hackers, OSS contributors, max-privacy envs | anyone who'll want the watchlist-to-alert workflow once it ships |

Cache hits are the entire reason a $29/mo Solo plan can sustain healthy gross margin: the same Korean filing title gets translated once, then served to every other tenant on the same plan from KV. See [`docs/CLAUDE_DESKTOP.md`](docs/CLAUDE_DESKTOP.md) for the env-var split between modes.

> **Hosted HTTP transport (no local install) — live today.** [Smithery](https://smithery.ai/servers/whdrnr2583/koreanpulse) distributes the MCP via their hosted gateway at `https://koreanpulse--whdrnr2583.run.tools`. MCP clients (Claude Desktop, Cursor, any client supporting Streamable HTTP) can connect directly without `pip install`. The local stdio install path remains the canonical way for self-hosters and max-privacy users; a first-party Cloudflare-hosted HTTP transport is still on the roadmap for users who want the endpoint outside Smithery.

## Legal posture

- Korean news: **fair-use summaries with attribution + outbound links**, no full-text republication.
- DART, government data: **public, free to redistribute** with attribution.
- Korean broker reports: **public-facing summaries only** (paywalled reports excluded).
- No spatial / mapping data → 공간정보관리법 무관.
- No investment advice → 자본시장법 유사투자자문업 무관 (data + summary only).

## Billing (Lemon Squeezy webhook on Cloudflare D1)

Billing runs on the [`webhook-worker/`](webhook-worker/README.md) Cloudflare Worker + D1 (SQLite). The operator runs **zero servers**. See [`webhook-worker/README.md`](webhook-worker/README.md) for the full deploy + secrets walkthrough; the short version:

```bash
cd webhook-worker
npm install
npx wrangler d1 create koreanpulse_db   # paste returned id into wrangler.toml
npm run migrate:prod                     # applies 0001_licenses.sql + 0002_pricing_v2.sql

# Required secrets
npx wrangler secret put LEMONSQUEEZY_WEBHOOK_SECRET
npx wrangler secret put KOREANPULSE_CACHE_SHARED_SECRET   # same value cache-worker uses

# Active pricing v2 variants (one per published tier)
npx wrangler secret put LEMONSQUEEZY_VARIANT_SOLO         # Cloud Solo $29/mo
npx wrangler secret put LEMONSQUEEZY_VARIANT_ANALYST      # Cloud Analyst $79/mo
npx wrangler secret put LEMONSQUEEZY_VARIANT_DESK         # Cloud Desk $249/mo

# Design Partner lifetime (private 20-seat SKU; see footnote in Pricing)
npx wrangler secret put LEMONSQUEEZY_VARIANT_LIFETIME

# Deprecated / back-compat slots (leave unset in production):
#   LEMONSQUEEZY_VARIANT_PRO / _STARTER / _INDIE / _ENTERPRISE
npm run deploy
```

Endpoints (deployed to `https://api.koreanpulse.dev` or `https://koreanpulse-webhook.<account>.workers.dev`):

- `GET /health` → `{"status":"ok"}`
- `POST /webhook/lemonsqueezy` → HMAC-SHA256 signature verified, idempotent on `meta.webhook_id`
- `POST /v1/validate` → HMAC-signed by the cache-worker, validates license + atomically increments period counter

Handles: `subscription_created` / `_updated` / `_cancelled` / `_payment_success` / `_payment_failed` / `order_created` (lifetime deal). Auto-issues license keys, upgrades plans in place, resets period counters on renewal, preserves lifetime licenses past subscription cancellation.

The earlier path (Python `koreanpulse-webhook` FastAPI on Lightsail + Postgres) is **superseded** as of 2026-05-05; for operator memory it lives at [`docs/legacy/POSTGRES_LIGHTSAIL.md`](docs/legacy/POSTGRES_LIGHTSAIL.md). New deploys should use the Cloudflare Worker path.

## Distribution / marketplaces

Listing copy + submission checklists in [`docs/MARKETPLACE.md`](docs/MARKETPLACE.md):

- [Smithery](https://smithery.ai/servers/whdrnr2583/koreanpulse) — **live**, hosted HTTP gateway included
- [PulseMCP](docs/listings/PULSEMCP.md) — submitted (hand-reviewed)
- [Glama](docs/listings/GLAMA.md) — submitted (pending review)
- [Awesome MCP](https://github.com/punkpeye/awesome-mcp-servers) — [PR #5893](https://github.com/punkpeye/awesome-mcp-servers/pull/5893)
- MCP Market — Smithery ingest (auto)

Beta acquisition (50 users in 30 days) plan + crypto-native channel mix in [`docs/BETA.md`](docs/BETA.md). Demo recording script in [`docs/DEMO.md`](docs/DEMO.md). CI / PyPI release pipeline in [`docs/CI.md`](docs/CI.md).

## Real-time alerts (Discord / Telegram / Slack)

Crypto-native rotators want pings, not dashboards. `koreanpulse.alerts.send_alert(url, title=, body=)` sends to any of:

- Discord webhooks (`https://discord.com/api/webhooks/...`)
- Slack incoming webhooks (`https://hooks.slack.com/services/...`)
- Telegram bots (shortcut `tg://<bot_token>/<chat_id>` or full `sendMessage` URL)

Fire-and-forget — transport / formatting failures return `AlertResult(ok=False)` instead of raising, so an outage in one channel never breaks a tool call. See `src/koreanpulse/alerts.py`.

## License

Source: AGPL-3.0. Hosted service: commercial.
