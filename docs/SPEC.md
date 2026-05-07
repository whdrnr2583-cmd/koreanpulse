# koreanpulse — product spec (v0)

Working spec. Will iterate as we ship.

## Customer persona — `Sarah, Solo Korea Analyst`

- 30s, MBA, covers Asian equities at a $500M long/short fund based in NYC
- Rotation includes Korea (~15% of book)
- Reads English wires (KED Global, Korea Bizwire) but feels she misses 80% of Korean primary signal
- Uses Claude Desktop daily for summaries
- Already pays $200/mo for Substack newsletters about Korea
- Discretionary research budget: ~$300/mo
- **Sweet-spot plan: Cloud Analyst $79/mo**

## Customer persona — `Daniel, EM activist analyst`

- Boutique fund, 8 ppl, NYC + Singapore
- Watching Korean activist scene heat up (KCGI, Align Partners)
- Needs early warning when activists file disclosures or build positions
- Currently relies on bilingual interns
- **Sweet-spot plan: Cloud Analyst $79/mo (saved searches + multi-channel alerts), Cloud Desk $249/mo if multiple analysts on the team need access**

## Customer persona — `Mia, K-content / EM journalist`

- Freelance, covers Korea for English-language outlets
- Trial budget $30/mo
- **Sweet-spot plan: Cloud Solo $29/mo**

## Customer persona — `Jay, crypto-native rotator` (★ primary ICP for v0)

Added 2026-05 as the actual launch ICP after observing the rotation pattern
into Korean equities from on-chain.

- Late 20s / early 30s, was running 6–7 figs on Hyperliquid / Bybit perps
- Rotated 30–60% of book into KOSPI / KOSDAQ small-mid caps (2025–2026)
- Lives in Discord (Hyperliquid, Solana trading, ASXN, a few private rooms)
- Uses Claude Desktop daily; Cursor for the small Python tools they hack
- Reads English, copies Korean tweets / filings into ChatGPT for context
- **Pays in the $20–200/mo range** without budget approval — personal card
- Hates sales calls. Hates demos. Will install an MCP server in 5 minutes
  if the README is good
- The single most-requested feature: **Discord webhook alerts**
  ("when X event happens, ping my server")
- **Sweet-spot plan: Cloud Solo $29/mo on day 1 (Discord channel hooked up immediately); Cloud Analyst $79/mo if they grow into multi-channel + saved searches**

Implications already baked into the build:
- `monitor_activist_investors` tool — high-signal, low-noise, exactly the
  data this persona traded around in crypto (whale wallet movements →
  insider/activist filings)
- `koreanpulse.alerts` module — Discord / Telegram / Slack webhook
  delivery, fire-and-forget, no UI required
- `list_filings_cached` with 60s TTL on today's window — real-time enough
  for non-HFT rotators
- Pricing focus on workflow tilt — Solo $29/mo is the floor for getting
  a Discord ping when something material moves
- Marketing copy: "Watchlist in, English alert out. The MCP plumbing is an
  implementation detail."

## MVP slice — what shipped

Three tools end-to-end, plus two helpers:

### `track_korean_filings`

DART filings with optional server-side translation/summary. Cached aggressively.

```
Input:
  company_corp_code: str | None  # use lookup_corp_code first
  days: int = 7        # 1–30
  filing_type: str | None  # A–J (DART codes)
  limit: int = 30
  translate: bool = True
  summarize: bool = False
Output:
  list[Filing]  # DART URL + KR title + EN title (if translate) + EN summary (if summarize)
```

### `lookup_corp_code`

Korean company name → DART 8-digit corp code. First call downloads ~5MB index, cached 7 days.

### `resolve_stock_code`

KRX 6-digit code → corp entry.

### `search_korean_industry_news`

Aggregates Korean industry RSS (etnews, 한국경제) and classifies into 16 industries:
semiconductor, shipbuilding, battery, biotech, defense, auto, ev_charging, ai,
steel, petrochem, construction, fintech, gaming, ecommerce, telco, energy.

### `koreanpulse_about`

Server info, tool list, corp index size.

## Pricing

Public-facing tiers — workflow-priced, three Cloud tiers + an OSS lane:

| Tier | $/mo | Watchlists | Queries/mo | Archive | Alert channels |
|---|---|---|---|---|---|
| **Cloud Solo** | 29 | 5 | ~2,000 | 30 days | 1 (Discord or Telegram) |
| **Cloud Analyst** | 79 | 25 | ~15,000 | 1 year | Multiple (Discord / Telegram / Email) |
| **Cloud Desk** | 249 | shared, 3 seats | ~100,000 | 1 year + team archive | Slack / webhooks |

Annual: **−20%** on all Cloud tiers. Public Free (web only) at `/today` — `/today.json`, last-3-day archive, no login, no MCP, no alerts. OSS self-host with own DART + OpenAI keys for hackers — community support only, **not a pricing tier**, separate "Run it yourself" lane in the README. Enterprise / SLA: contact us (no published price). _Design partner program available for the first 20 named seats — contact us; not promoted publicly._

### Why this pricing

Pricing v2 (2026-05-05) — workflow-priced ladder replacing the previous Free / Pro $19 / Lifetime $99 structure. The old Pro $19 unmetered tier was retired because the model is now "we ping you when X moves" rather than "we are an MCP server you query":

- **Cloud Solo $29/mo**: floor tier for the watchlist-to-alert workflow. 5 watchlists + 1 Discord/Telegram channel = the Jay persona's day-one need.
- **Cloud Analyst $79/mo**: the real revenue tier. Boutique fund analysts and paid-research-budget retail traders get 25 watchlists, 1-year archive search, multi-channel alerts, saved searches, CSV/JSON export, priority cache. Sized to be a single-line research-budget item ($79 < typical Substack stack).
- **Cloud Desk $249/mo**: small research teams and boutique long/short desks. 3 seats, shared watchlists, Slack/webhook alerts, ~100,000 queries, team archive.
- **OSS self-host**: AGPL source + own DART + OpenAI keys. Surfaced in README + a future `docs/SELF_HOSTING.md` block, **not in the pricing table**. Community support only. No alerts, no hosted archive, no shared translation cache, no account sync. (Cloud customers also install the MCP locally today — a true HTTP-transport remote MCP is on the Q3 2026 roadmap.)
- **Design Partner Lifetime $299** (private, 20-seat cap, contact-only): footnote-only mention in README and one operator doc. Never on landing or in marketplace listings.
- **Public Free** (`/today`, `/today.json`, last-3-day archive): preserved as SEO + funnel + AI-crawler surface, positioned as a teaser, not a pricing tier.

## Capacity

DART caps each key at **40,000 calls/day**. We soft-cap at 32,000/day (80%) with `DART_DAILY_QUOTA` env override.

### Filing list cache (the load-bearing layer)

`list_filings_cached()` wraps every DART filings call with a freshness-aware TTL:

| Window | TTL | Why |
|---|---|---|
| `end_de` ≥ today | 60s | new filings can appear minute-to-minute |
| 1–6 days old | 1 hour | recent, may be amended |
| ≥ 7 days old | 24 hours | effectively immutable |

Key = SHA256 of `(corp_code, bgn_de, end_de, pblntf_ty, page)`. Same query from any tenant → cache hit → **0 DART quota consumed**, daily counter doesn't increment.

Verified live 2026-05-04: same query from process restart still hit cache, 1 DART hit per unique query regardless of caller count.

### Customer capacity by cache hit rate

| Cache hit | Effective DART ceiling | Customer calls/day |
|---|---|---|
| 0% (no cache) | 32,000 | 32,000 |
| 50% (cold start) | 64,000 | 64,000 |
| **70% (3-mo realistic)** | **107,000** | **107,000** |
| 85% (mature) | 213,000 | 213,000 |

### MAU capacity matrix (assumes 30% MAU→DAU)

Avg DART filings per active user/day estimated from the per-plan limits:

| Plan | Avg filings/DAU/day |
|---|---|
| Public Free (web only) | 0 (no MCP) |
| OSS self-host | 5 |
| Cloud Solo | 10 |
| Cloud Analyst | 60 |
| Cloud Desk | 200 (team) |

Translated to MAU ceiling at each cache hit rate:

| Cache hit | Comfortable MAU | Peak MAU |
|---|---|---|
| 0% (no filing cache, current state before this PR) | 800 | 3,000 |
| 70% (post-cache, realistic) | 9,500 | 32,000 |
| 85% (mature) | 19,000 | 64,000 |
| 95% (high reuse) | ~25,000 | DART-limited |

Hard ceiling: **~30,000 MAU per DART key** even at 100% cache. Beyond that, second key (separate 사업자등록번호) required.

### 12-mo forecast vs capacity

Per current paid-mix forecast under workflow-priced ladder (~600 active subscribers + a long tail of OSS self-hosters and Public Free visitors):

| Plan | MAU | DAU(30%) | Filings/day each | Total filings/day |
|---|---|---|---|---|
| OSS self-host | 300 | 90 | 5 | 450 |
| Cloud Solo | 200 | 60 | 10 | 600 |
| Cloud Analyst | 80 | 24 | 60 | 1,440 |
| Cloud Desk (3-seat teams) | 20 (teams ~7 MAU) | 6 | 200 | 1,200 |
| **Total** | **600** | **180** | | **~3,690 customer filings/day** |

At 70% cache hit → **~1,100 DART calls/day** → **~3.4% of 32K soft quota** → **~30× headroom**. Room to scale to ~25,000 MAU before quota engineering. Public Free (web-only) traffic does not consume DART in the per-user path — only the daily cron build does.

## Revenue forecast (12mo, workflow-priced ladder)

| Mix | MRR |
|---|---|
| 200 Cloud Solo @ $29 | $5,800 |
| 80 Cloud Analyst @ $79 | $6,320 |
| 20 Cloud Desk @ $249 | $4,980 |
| **Total MRR** | **$17,100** |

OSS self-host generates $0 (intentional). Public Free generates $0 (intentional, funnel surface). Design Partner Lifetime $299 cohort (private, 20-seat cap): 20 × $299 = $5,980 — booked once, not part of MRR.

### Cost model — per customer LLM cost (GPT-5-mini default)

500 input + 200 output tokens per LLM call. With 80% cache hit, 1 LLM call per 5 customer calls.

| Plan | Customer calls/mo | Real LLM calls (after 80% cache) | LLM cost/mo | Margin |
|---|---|---|---|---|
| OSS self-host | n/a (user pays OpenAI directly) | 0 on our side | $0 | n/a |
| Cloud Solo $29 | ~2,000 | 400 | $0.21 | 99.3% |
| Cloud Analyst $79 | ~15,000 | 3,000 | $1.58 | 98.0% |
| Cloud Desk $249 | ~100,000 | 20,000 | $10.50 | 95.8% |

Aggregated cost across the 12mo customer mix: **~$380/mo total LLM spend** vs $17,100 MRR → **~97.8% gross margin**. OSS self-host costs us nothing in LLM spend (BYOK on the self-hoster's keys).

(Switching to Claude Haiku 4.5 raises LLM cost ~3× — still ~94% margin on the Cloud tiers, no business issue.)

**1억/년 비현실 박제 그대로 적용** — this is secondary income, not a hyperscale bet.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| MCP framework | **FastMCP** (Python) | 70% market share, sticks to spec |
| Web stack | FastAPI + httpx | Reuse from agentprod |
| LLM (translation/summary) | **OpenAI GPT-5-mini** (default) or Claude Haiku 4.5 | $0.25/M in + $2/M out — ~3× cheaper than Haiku at similar/better quality. Provider switchable via env. |
| Cache | File JSONL → Supabase Postgres | File for v0 simplicity, swap when scale demands |
| Auth | Supabase Auth + license-key MCP middleware | Same flow already validated |
| Billing | **Polar** sole provider (active 2026-05-06+); Lemon Squeezy not in use, store application declined 2026-05-06 | Polar acts as MoR — VAT/sales tax/refunds handled |
| Hosting | AWS Lightsail Seoul + Vercel landing | Already provisioned |

## Throttle / cost discipline

- Wrap *all* outbound calls (DART, news scrapers, LLM) with `agentprod.Throttle`
- Track per-tenant cost via `agentprod.CostTracker(labels={"tenant": ...})`
- DART soft daily cap (32K/day) enforced before send
- Auto-cutoff at plan quota (return `[koreanpulse:quota_exceeded] ...`)

## What's NOT in MVP

- **Watchlist polling + alert dispatch**: in-flight. Schema (D1 + Postgres) and `koreanpulse.alerts` primitives shipped; the cron loop wiring them together is the missing piece. Promised to Solo / Analyst / Desk customers as the load-bearing feature, lands in this release window.
- Earnings call transcription (post-MVP)
- M&A pipeline (post-MVP)
- Multi-seat / SSO beyond Cloud Desk's 3 seats (deferred — contact-us SLA for larger teams)
- Email digest (post-MVP)
- Mobile app / native iOS-Android push (deferred; Discord/Telegram covers most)

## Failure signals (pre-defined)

- 6mo: < 100 free signups (Public Free + OSS self-host combined) → discovery fail
- 6mo: 0 paid Cloud subscribers → pricing or audience fail
- 12mo: < $1,000 MRR → niche too narrow, sunset or pivot
- 30-day beta cohort Cloud-tier conversion < 5% → audience pivot needed (see `BETA.md`)
- Bloomberg launches Korean indie tier → re-evaluate within 30 days
