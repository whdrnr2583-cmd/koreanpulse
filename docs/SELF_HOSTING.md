# Run koreanpulse yourself (OSS self-host)

This guide is for hackers who want to run the MCP server entirely on their
own machine — own DART API key, own OpenAI/Anthropic key, no license, no
account. The paid Cloud Solo / Analyst / Desk tiers are a different path
(see [`README.md`](../README.md) "Pricing" + [`docs/CLAUDE_DESKTOP.md`](CLAUDE_DESKTOP.md)).

> **Why self-host?** Privacy — translation traffic never leaves your laptop
> + your provider account. No license server in the loop. AGPL source you
> can audit and fork. Best for solo devs, privacy-strict environments, or
> anyone who already pays for OpenAI and doesn't need the workflow features
> (watchlists / alerts / archive / hosted cache).

> **Why pay for Cloud?** You don't have to manage the OpenAI bill. Cross-
> tenant translation cache makes repeat queries near-free. Workflow
> features (watchlists, alerts, archive search) ship under Cloud — they're
> planned (no date) and not in the OSS path.

## What you give up by self-hosting

| Feature | Self-host | Cloud (Solo / Analyst / Desk) |
|---|---|---|
| Free MCP tools (track filings, lookup corp, resolve ticker, search news, about) | ✅ | ✅ |
| License-gated tools (`monitor_activist_investors`, `monitor_foreign_holders`) | ❌ (hosted service only) | ✅ on the hosted service (paused since 2026-09-21) |
| `/today` daily web snapshot | ✅ (free public, no install) | ✅ |
| Translation cache | local JSONL file | global Cloudflare KV (cross-tenant reuse) |
| OpenAI / Anthropic key | yours | ours |
| Watchlists | ❌ | planned — not yet available |
| Discord/Telegram/Email alerts | ❌ | planned — not yet available |
| Archive search (30d / 1y) | ❌ | planned — not yet available |
| Account sync, multi-seat | ❌ | planned — not yet available (Desk) |
| Support | community (GitHub issues) | priority for Desk |

## Install

```bash
pip install koreanpulse
```

This installs the `koreanpulse` console script (PyPI release 0.1.13). It runs
the 5 free tools. The two license-gated tools (`monitor_activist_investors`,
`monitor_foreign_holders`) are not included in a self-install: they run only
on the hosted service, which is paused since 2026-09-21.

For development, clone the repo and install it in editable mode instead:

```bash
git clone https://github.com/whdrnr2583-cmd/koreanpulse.git
cd koreanpulse
pip install -e .
```

## Required env

| Var | Required | Purpose |
|---|---|---|
| `DART_API_KEY` | **yes** | DART OpenAPI access. Free at <https://opendart.fss.or.kr/>. 40,000 calls/day per key. |
| `OPENAI_API_KEY` | recommended | Server-side translation (default model: `gpt-5-mini`). Without it, tools return Korean-only fields. |
| `ANTHROPIC_API_KEY` | optional | Alternative provider when `KOREANPULSE_TRANSLATE_PROVIDER=anthropic`. |

Self-host runs in `KOREANPULSE_CACHE_MODE=local` by default — no further
config needed. Local state (corp-code index, translation and filing caches,
cost log) lives in `./.data`; if the working directory is not writable —
Claude Desktop and other GUI clients often launch the server with `cwd=/` —
it falls back to `~/.koreanpulse`. Set `KOREANPULSE_DATA_DIR` to choose the
location yourself. Translations cache to `<state dir>/cache/translate.jsonl`.

On start-up the server logs (stderr, so it shows in the client's MCP log) the
state directory and any missing configuration: no `DART_API_KEY`, or no
translation key.

## Claude Desktop config

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "koreanpulse": {
      "command": "koreanpulse",
      "env": {
        "DART_API_KEY": "your-dart-key-here",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

GUI apps do not inherit your shell `PATH`. If Claude Desktop shows the server
as disconnected, put the absolute path in `command` (find it with
`which koreanpulse`, or `where koreanpulse` on Windows), or run it through
Python:

```json
"command": "/full/path/to/python", "args": ["-m", "koreanpulse.server"]
```

Restart Claude Desktop. You should see `koreanpulse` in the MCP tools list
(seven tools; the two license-gated ones answer with a license-required
notice on a self-install).

## Try it

```
Use koreanpulse to find Samsung Electronics in DART and show me their
last 7 days of filings, translated to English.
```

Claude calls `lookup_corp_code('삼성전자')` → `track_korean_filings(company_corp_code=..., days=7, translate=true)`.

Results are a plain list when complete. When there is something to tell the
agent — nothing found in the window, more pages (`next_page`), a company or
news source that failed, translation unavailable — the tool returns
`{"filings": [...], "notes": [...], "window_kst": {...}}` instead; read
`notes` before concluding "nothing happened".

## DART quota math (yours, not ours)

- DART caps each API key at 40,000 calls/day.
- The MCP server enforces a soft cap at 32,000/day (80%, override via
  `DART_DAILY_QUOTA` env).
- Self-host uses **your** DART key, so the quota is yours alone — no
  multi-tenant cache to amortize against.
- Filing-list responses are cached locally with freshness-aware TTL
  (60s for today, 1h for 1–6d old, 24h for 7d+). Repeated queries
  inside a session are free.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `DartError: DART_API_KEY env var is missing` | Set `DART_API_KEY` in the Claude Desktop config `env` block (or your shell). |
| `DART_API_KEY is still the placeholder from .env.example` | You copied `.env.example` without replacing the key. |
| `DART 010: ... not registered` / `DART 011` / `DART 012` | Key not registered / suspended / restricted to other IPs. Check it at <https://opendart.fss.or.kr/>. |
| `title_en` empty and a `notes` entry says no translation backend is configured | Set `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` + `KOREANPULSE_TRANSLATE_PROVIDER=anthropic`). Without a key the tools still work and return Korean text. |
| `DartDailyQuotaExceeded` | You hit your local soft cap (`DART_DAILY_QUOTA`, default 32,000). Wait until KST midnight rollover. |
| `DartRateLimited` / `DART 020` | DART itself says the key's 40,000 calls/day are used up. Resets at KST midnight; cached queries still work. |
| A tool says `INCOMPLETE SCAN` | The window held more filings than `KOREANPULSE_MAX_SCAN_PAGES` × 100; narrow `days` or pass `company_corp_code`. |
| `must be an 8-digit DART corp_code` | You passed a ticker or a name. `resolve_stock_code` (ticker) or `lookup_corp_code` (name) return the corp_code. |
| `lookup_corp_code("Hyundai Motor")` finds nothing | The DART index is Korean. About 35 very well-known companies also resolve from their English name; otherwise search the Korean name (`현대자동차`). |
| Translation looks wrong / hallucinated | Try `KOREANPULSE_TRANSLATE_PROVIDER=anthropic` (Claude Haiku). Different system prompt, different failure modes. |

## Upgrading to Cloud later

The hosted service has been paused since 2026-09-21, so Cloud is on hold:
licenses cannot currently be used from a self-install, and the two
license-gated tools are unavailable. The steps below apply once it resumes.

If you decide your time is more valuable than your OpenAI bill:

1. Subscribe to a Cloud tier (Solo $29 / Analyst $79 / Desk $249).
2. You'll receive a license key (`kp_…`) by email.
3. Edit your Claude Desktop config:
   ```json
   "env": {
     "DART_API_KEY": "your-dart-key-here",
     "KOREANPULSE_CACHE_MODE": "hosted",
     "KOREANPULSE_LICENSE_KEY": "kp_..."
   }
   ```
4. Drop `OPENAI_API_KEY` (we hold it for you now).
5. Restart Claude Desktop.

Translation now goes through our Cloudflare Worker → global KV cache → our
OpenAI key. The same Korean filing title translated by you is reused for
every other Cloud customer instantly.

The MCP install path stays identical — Cloud is "hosted translation behind
local MCP", not a remote endpoint.

## Limits + license note

- Source code: AGPL-3.0-or-later (`LICENSE`). Network use of a modified
  version requires offering the source.
- Hosted Cloud service: commercial. Don't redistribute the hosted endpoint
  result as your own service.
- DART data: public, free redistribution with attribution.
- Korean news: fair-use summaries with attribution + outbound links.
  No full-text republication.
- No investment advice surface — koreanpulse is data + translation, not
  recommendations. Korean securities law (자본시장법 유사투자자문업) is not
  triggered.

## Related docs

- [`README.md`](../README.md) — project overview, pricing, architecture
- [`docs/CLAUDE_DESKTOP.md`](CLAUDE_DESKTOP.md) — Cloud-mode config alongside self-host
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — how the pieces fit
- [`docs/RUN_LIVE.md`](RUN_LIVE.md) — end-to-end smoke test
- [`webhook-worker/README.md`](../webhook-worker/README.md) — license/billing infrastructure (Cloud only)
