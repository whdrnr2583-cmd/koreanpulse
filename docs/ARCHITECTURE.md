# Architecture

Module-by-module breakdown of what runs where, what talks to what, and
which design constraints drove which choices. As of **2026-05-05** the
operator runs **zero servers** — everything customer-facing lives on
Cloudflare (3 Workers + D1 + KV), the MCP itself runs locally on the
customer's machine.

> **Status note (2026-05-05).** Watchlist polling + alert dispatch are
> on the Q3 2026 roadmap; today the customer-facing surface that ships
> is queries (DART filings + classification + foreign-holder + activist
> tracking + industry news) and the hosted translation cache. The
> alert primitives (`koreanpulse.alerts`) and per-tier limit constants
> (`PLAN_LIMITS`) ship in code, but the polling loop that wires them
> into the customer's watchlist is not yet ticking.

## High-level shape

```
                              ┌──────────────────────┐
                              │  Claude Desktop /    │
                              │  Cursor / any MCP    │
                              │  client              │
                              └─────────┬────────────┘
                                        │  stdio (JSON-RPC)
                                        ▼
                              ┌──────────────────────┐
                              │ koreanpulse.server   │
                              │   FastMCP            │
                              │   7 tools registered │
                              │   (runs locally on   │
                              │   customer machine)  │
                              └────┬───────┬─────┬───┘
              ┌────────────────────┘       │     └──────────────────┐
              │ DART API                   │ Cache Worker           │ news (RSS)
              │ (always direct,            │ (when cache_mode=      │ etnews,
              │  customer's key)           │  hosted; license-gated)│ hankyung
              ▼                            ▼                        ▼
     ┌────────────────┐    ┌────────────────────────┐       ┌───────────────┐
     │  opendart.fss  │    │  Cache Worker (CF)     │       │  RSS feeds    │
     │  .or.kr        │    │   /v1/translate        │       │  (direct)     │
     └────────────────┘    │   /v1/summarize        │       └───────────────┘
                           │   KV translation cache │
                           │   holds OPENAI_API_KEY │
                           └────────────┬───────────┘
                                        │ HMAC-signed
                                        │ /v1/validate
                                        ▼
                           ┌────────────────────────┐
                           │  Webhook Worker (CF)   │
                           │   /webhook/            │
                           │     lemonsqueezy       │
                           │   /v1/validate         │
                           │   D1 (SQLite):         │
                           │     licenses           │
                           │     webhook_events     │
                           └────────────┬───────────┘
                                        ▲
                                        │ HMAC-verified webhook POST
                                        │
                           ┌────────────┴───────────┐
                           │  Polar (active)        │
                           │  (Merchant of Record)  │
                           │                        │
                           │  Lemon Squeezy: dormant│
                           │  (handler kept; no LS  │
                           │   secrets in prod)     │
                           └────────────────────────┘

      Independent: Daily Worker (cron, builds /today)

                           ┌────────────────────────┐
                           │  Daily Worker (CF)     │
                           │   cron 30 7 * * 1-5    │
                           │   (KST 16:30 weekdays) │
                           │   /today (HTML)        │
                           │   /today.json          │
                           │   /today/YYYY-MM-DD    │
                           │   KV snapshot store    │
                           └────────────┬───────────┘
                                        │ optional
                                        ▼
                                Discord webhook push
                                (fire-and-forget)

      Roadmap (Q3 2026): polling loop wiring watchlists → alert dispatch.

      ┌──────────────────────┐         Discord / Slack / Telegram
      │ koreanpulse.alerts   │ ──────▶  webhook delivery (fire-and-forget)
      │  (primitive shipped, │         (the cron loop that calls this on
      │   not yet wired into │          watchlist matches is Q3 2026)
      │   watchlist polling) │
      └──────────────────────┘
```

## Processes / surfaces

| Surface | Where it runs | What it does | Status |
|---|---|---|---|
| `koreanpulse` MCP server | Customer's machine (stdio under Claude Desktop / Cursor / any MCP client) | DART filings + corp lookup + activist/foreign-holder tracking + industry news + translation dispatch | Live |
| Cache Worker | Cloudflare Workers + KV | Hosted translation cache, holds our OpenAI key, license-gated | Live |
| Webhook Worker | Cloudflare Worker + D1 | **Polar** webhook handler + license validation endpoint (Lemon Squeezy handler kept dormant) | Live |
| Daily Worker | Cloudflare Workers + KV (cron) | Builds `/today` daily snapshot, optional Discord push | Live |
| Watchlist polling loop | (Q3 2026) — likely a fourth Worker cron consuming the D1 watchlist table | Cron-pulls DART changes for each watchlist, calls `koreanpulse.alerts` on hits | **Roadmap** |
| True remote MCP transport | (Q3 2026) — HTTP-transport Worker so customers don't `pip install` | Eliminates local install for Cloud customers | **Roadmap** |

## Module responsibilities

### `koreanpulse._env`

`.env` autoloader. Imported eagerly from `__init__.py` so submodules see
populated `os.environ` even before any explicit call. Search order:
`KOREANPULSE_ENV_FILE` → `./.env` → repo-root `.env`. Never overrides
existing env.

### `koreanpulse.sources`

Single source of truth for **where** we pull from. RSS feeds for industry
news (etnews, hankyung) plus DART API constants and filing-type label map.
Adding a new news source is one entry here.

### `koreanpulse.cache`

`FileCache(root)` — append-only JSONL per namespace, lazily loaded into
memory. Optional per-entry `ttl_seconds`. Same interface implements
`NullCache` for tests / opt-out. `Cache` is a Protocol so swapping for
Redis / Postgres is one class.

Key namespacing: `<namespace>:<sha256-prefix>`. Translations live in
`translate:`, summaries in `summarize:`, filing lists in `dart_list:`.

### `koreanpulse.dart`

DART OpenAPI client. Three things:

1. **Daily soft quota** (`DART_DAILY_QUOTA`, default 32 000) enforced
   before every outbound call via `_bump_daily_counter()`. Raises
   `DartDailyQuotaExceeded` cleanly so callers can surface a 402.
2. **Throttle** — agentprod token bucket at 5 req/s burst, jittered, to
   stay below DART's empirical per-key burst cap (~10/s).
3. **`list_filings_cached`** — same shape as `list_filings`, but goes
   through the FileCache with a freshness-aware TTL:
   - end_de ≥ today → 60s
   - 1–6 days old → 1 hour
   - ≥ 7 days old → 24 hours

The `_classify_filing_type()` heuristic infers DART filing-type code (A–J)
from the title — DART's `list.json` does **not** include `pblntf_ty` in
its responses, so the title is the only signal at list-time.

### `koreanpulse.corp_code`

DART corp-code index. The full XML (~5 MB, ~117 k entries) is downloaded
once and cached on disk for 7 days. In-memory dicts keyed by name
(substring match) and stock_code (exact). First lookup pays the download
cost; everything after is local.

### `koreanpulse.news`

RSS aggregator. Currently 2 active feeds (etnews, hankyung), 2 placeholders
(MK, ChosunBiz) without RSS. Each item gets:

- `industries`: multi-label tag set drawn from `INDUSTRY_KEYWORDS` (16
  industries, Korean substring match)
- `relevance_score`: 0.4 + 0.15 per matched tag, capped at 1.0
- `attribution`: required string per source

Keyword classification is deliberately cheap (substring match against
Korean keywords). Replace with a fine-tuned classifier later if precision
becomes a problem.

### `koreanpulse.translate`

Server-side LLM with provider abstraction. Two providers shipping:

| Provider | Default model | $/M in | $/M out |
|---|---|---|---|
| openai *(default)* | gpt-5-mini | $0.25 | $2.00 |
| anthropic | claude-haiku-4-5-20251001 | $1.00 | $5.00 |

Cache key includes the provider, so swapping providers doesn't poison
prior translations. Cost tracked per call via `agentprod.CostTracker`
with provider + op labels.

`KOREANPULSE_TRANSLATE_MODEL` env override only applies to the **default**
provider — that prevents `provider="anthropic"` from accidentally picking
up a `gpt-*` model name from env.

`KOREANPULSE_CACHE_MODE` switches between local (your OpenAI key, local
JSONL cache) and hosted (Cache Worker holds key, global KV cache, license
key required).

### `koreanpulse.license`

`Plan` enum + `License` dataclass + `InMemoryLicenseStore` + the
`validate_license_or_raise` gate function used by the MCP server.

`PLAN_LIMITS` defines `calls_per_month`, `watchlists`, `alert_channels`,
`seats`, `retention_days` for each plan. **As of 2026-05-05 only
`calls_per_month` is enforced at runtime**; the other limits ship as
paper constants until the polling loop and CRUD endpoints land in Q3
2026. Customer-facing copy reflects this.

### `koreanpulse.activists`

Korean activist-investor allowlist. 10 entries, each with both Korean and
English aliases. `match_activist(filer_name)` returns the canonical
English label or None. Used by the `monitor_activist_investors` tool to
flag DART type-D shareholding disclosures.

### `koreanpulse.alerts`

Outbound webhook delivery to Discord / Slack / Telegram. URL auto-detect
(`detect_channel`) + per-channel payload formatting (Discord embed,
Slack Block Kit, Telegram Markdown). All delivery errors trapped — a
broken webhook never propagates into the calling tool.

Telegram supports both shortcut form (`tg://<bot_token>/<chat_id>`) and
full sendMessage URL (`https://api.telegram.org/bot.../sendMessage?chat_id=...`).

The primitive ships today; the cron polling loop that calls it on
watchlist matches is Q3 2026.

### `koreanpulse.models`

Pydantic public types. Stable surface — these get serialized into MCP
tool responses, so changes here are breaking.

- `Filing` — one DART filing
- `ActivistFiling(Filing)` — adds `is_likely_activist`, `activist_label`
- `ForeignHolderFiling(Filing)` — adds `holder_label`, `holder_origin`
- `Article` — one news item (title_ko, title_en, summary_en, industries…)

### `koreanpulse.server`

FastMCP wire-up. Registers seven tools, holds the singleton `_cache` /
`_cost_tracker` / `_translator`, gates each tool through
`validate_license_or_raise` when `KOREANPULSE_REQUIRE_LICENSE=1`.

| Tool | DART hits per call | Translation? |
|---|---|---|
| `track_korean_filings` | 1 (cache miss) / 0 (hit) | optional |
| `lookup_corp_code` | 0 (uses local 7d cache) | n/a |
| `resolve_stock_code` | 0 | n/a |
| `search_korean_industry_news` | 0 (RSS) | optional |
| `monitor_activist_investors` | 1 / 0 | optional |
| `monitor_foreign_holders` | 1 / 0 (shares the type-D fetch) | optional |
| `koreanpulse_about` | 0 | n/a |

### `webhook-worker/` (TypeScript Worker + D1)

Replaces the Python `koreanpulse-webhook` FastAPI app + Postgres store.
Three modules (~700 LOC):

- `src/license.ts` — D1 query helpers (`getByKey`, `findByEmail`,
  `nextLifetimeSeq`, `upsertLicense`, `incrementUsage`,
  `validateAndCharge`, `markEventSeen`, `issueLicenseKey`).
- `src/lemonsqueezy.ts` — HMAC-SHA256 verify (constant-time), 7-event
  dispatcher, role/self_description capture, idempotency via D1.
- `src/index.ts` — fetch handler for `/health`, `/webhook/lemonsqueezy`,
  `/v1/validate`. Mirrors the legacy Python webhook semantics 1:1.

D1 schema in `webhook-worker/migrations/0001_licenses.sql` — two tables:

- `licenses` — one row per issued license. Mirrors the Postgres schema
  in `migrations/001_licenses.sql` but with SQLite-compatible types
  (TEXT for timestamps, INTEGER for booleans, JSON-as-TEXT for metadata).
  Denormalised `is_lifetime` + `deal_seq` columns to keep lifetime
  accounting fast without a JSON functional index.
- `webhook_events` — idempotency log. PK on `webhook_id`.

### `cache-worker/` (TypeScript Worker + KV)

Hosted translation/summary cache. Holds the operator's `OPENAI_API_KEY`,
fronts a global Cloudflare KV cache, gates each call behind
`POST /v1/validate` to the webhook-worker (HMAC-signed). Successful
validate results cached in the per-colo Cache API for 60s; failures not
cached so a cancellation is picked up within seconds.

### `daily-worker/` (TypeScript Worker + KV, cron)

Cron-driven `/today` dashboard. KST 16:30 weekday cron pulls DART type-D
+ type-A/B filings, runs activist + foreign-holder matchers, calls
OpenAI gpt-5-mini for English titles + ≤80-word summaries +
"Today's takeaway" digest, writes HTML + JSON to KV, optionally pushes
to Discord. Routes: `/today`, `/today.json`, `/today/YYYY-MM-DD`,
`/admin/rebuild` (DART key as shared admin secret).

## Data flow — typical request

```
1. Customer asks Claude: "What did Samsung file with DART last week?"
2. Claude picks track_korean_filings (or lookup_corp_code first if needed).
3. Local koreanpulse.server:
   a. _gate(license_key)        → validates against LicenseStore (or via
                                   webhook-worker /v1/validate when
                                   hosted-mode upstream)
   b. list_filings_cached(...)  → dart_list:<hash> in cache?
       └─ MISS → DART API /list.json (customer's DART_API_KEY) → bump
                 daily counter → cache result with TTL
       └─ HIT  → return cached list, no DART traffic
   c. for each filing:
       title_en = translator.translate_ko_to_en(title)
         └─ KOREANPULSE_CACHE_MODE=local: translate:<hash> in JSONL
                                          cache? hit → return; miss →
                                          OpenAI (customer's key) →
                                          cache
         └─ KOREANPULSE_CACHE_MODE=hosted: POST cache-worker
                                           /v1/translate with license
                                           key → KV hit returns
                                           cached; KV miss runs OpenAI
                                           on the worker (our key) and
                                           writes back
4. Returned to Claude as JSON, rendered to user.
5. Cost ledger appended (.data/cost.jsonl) for local mode; webhook-
   worker increments period_calls in D1 for hosted mode.
```

## Performance / cost envelope

For the 12-month customer-mix forecast (~756 MAU mostly free + ~86 paying):

- DART traffic: **~930 calls/day** at 70% cache hit, 2.9% of soft quota
- LLM traffic: ~80 GPT-5-mini calls/day at 80% cache hit
- LLM cost: **~$2/month total** across all paying tiers (98.6% gross
  margin on $5,814 forecast MRR)
- Cloudflare Workers + KV + D1: $0 (free tier covers 100K req/day,
  several orders of magnitude past expected paid traffic)
- Storage: `.data/cache/*.jsonl` grows ~5 MB/month (translations are the
  biggest contributor) for OSS self-host; Cloud customers don't keep a
  local cache.

## Test surface

- 181 tests passing, 1 skipped (Postgres test needs a live DB)
- Unit tests cover every module; integration tests cover the legacy
  Python webhook via `fastapi.testclient.TestClient`
- DART tests use `httpx.MockTransport` — no live API required for CI
- Live verification path: `python examples/quickstart.py` (see RUN_LIVE.md)
- Webhook-worker tests live under `webhook-worker/` (TS / vitest)

## Why not <X>

- **Why FastMCP not raw MCP SDK?** FastMCP currently powers ~70% of
  shipped MCP servers. Sticks to spec, less plumbing.
- **Why Pydantic for tool returns?** FastMCP serializes them cleanly into
  MCP responses without manual JSON wrangling.
- **Why JSONL cache, not SQLite?** SQLite needs a connection per access;
  JSONL is dependency-free and fits the access pattern (write-heavy log,
  read-heavy with full namespace load on cold start).
- **Why GPT-5-mini default, not Claude Haiku?** 3× cheaper per token,
  benchmarks even or better for translation. Anthropic stays as fallback.
- **Why Cloudflare Worker + D1 instead of FastAPI on Lightsail?** Zero
  ops, $0 free tier, single dashboard for cache + daily + webhook
  workers + license store. The earlier Lightsail/Postgres path is now
  superseded — see [`legacy/POSTGRES_LIGHTSAIL.md`](legacy/POSTGRES_LIGHTSAIL.md).
- **Why no Sentry / Datadog?** Cost discipline. agentprod's CostTracker
  + Cloudflare's built-in analytics + Python logging is enough until
  paid customers > 10.

## Legacy

- [`legacy/POSTGRES_LIGHTSAIL.md`](legacy/POSTGRES_LIGHTSAIL.md) — the
  pre-2026-05-05 deployment path (FastAPI on Lightsail + Postgres
  store). Superseded by the Cloudflare Worker + D1 path. Retained for
  operator memory; do not stand up new instances on this path.
