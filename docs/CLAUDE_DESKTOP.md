# Hooking koreanpulse into Claude Desktop

Claude Desktop reads MCP server config from `claude_desktop_config.json`.
This guide covers both the **OSS self-host** path (you bring your own
DART and OpenAI keys, run the MCP locally — community support only) and
the **Cloud** path (you bring a Solo / Analyst / Desk license and we host
the watchlist-to-alert workflow + translation cache).

Cloud pricing reference: **Solo $29/mo · Analyst $79/mo · Desk $249/mo.**

## Quick decision: which mode?

| | OSS self-host (free) | Cloud Solo ($29/mo) |
|---|---|---|
| Local MCP install | required (`pip install koreanpulse`) | required (same install — only translation calls hit our Worker) |
| Provider key | your `OPENAI_API_KEY` | ours (you don't need one) |
| Translation cache | local `.data/cache/` only | global Cloudflare KV (cross-tenant reuse) |
| Per-call cost | OpenAI billed to you | absorbed into Solo |
| Watchlist polling + alerts | not included | **Q3 2026 ship target** (waitlist) |
| Hosted archive | none | **Q3 2026 ship target** (30 days) |
| License key required | no | yes (`kp_…`) |
| Support | community only (issues/PRs) | included |
| Best for | hackers, OSS contributors, max-privacy envs | anyone who'll want the watchlist-to-alert workflow once it ships |

> **Beta status (2026-05-05).** Watchlist polling, alert dispatch,
> per-tier limit enforcement (watchlist count, channel count, retention,
> seats), and the true HTTP-transport remote MCP (no local install) are
> all on the **Q3 2026** ship target. Today, signing up to a Cloud tier
> gets you: hosted English translation cache (no OpenAI key needed) +
> license-gated query metering (Solo 2K/mo / Analyst 15K/mo / Desk
> 100K/mo) + the locked-in launch rate. Public free `/today` snapshot is
> live too.

**Rule of thumb**: if you want to be pinged the moment a 5%-rule filing
hits one of your tickers, you want a Cloud tier — but the polling/dispatch
that powers that workflow ships Q3 2026. OSS self-host gets you the
engine, not the workflow. Subscribe at
<https://koreanpulse.dev/pricing> (Cloud Solo $29/mo, Cloud Analyst $79/mo,
Cloud Desk $249/mo) to lock in the launch rate.

## 1. Install koreanpulse

```bash
pip install -e .  # from this repo for now; PyPI later
```

This installs the `koreanpulse` console script.

## 2. Set env vars

### OSS self-host mode (default)

| Var | Required | Purpose |
|---|---|---|
| `DART_API_KEY` | **yes** | DART OpenAPI access. Free at <https://opendart.fss.or.kr/>. |
| `OPENAI_API_KEY` | recommended | Server-side translation (default model: `gpt-5-mini`). Without it, tools return Korean-only fields. |
| `ANTHROPIC_API_KEY` | optional | Alternative provider when `KOREANPULSE_TRANSLATE_PROVIDER=anthropic`. |
| `KOREANPULSE_TRANSLATE_PROVIDER` | optional | `openai` (default) or `anthropic`. |
| `KOREANPULSE_TRANSLATE_MODEL` | optional | Override model (default: `gpt-5-mini` for openai, `claude-haiku-4-5-20251001` for anthropic). |

### Cloud mode (paid: Solo / Analyst / Desk)

Drop `OPENAI_API_KEY` (the Cloudflare Worker holds it for you) and add:

| Var | Required | Purpose |
|---|---|---|
| `DART_API_KEY` | **yes** | Same as OSS self-host — DART access stays on your machine. |
| `KOREANPULSE_CACHE_MODE` | **yes** (`hosted`) | Switches the dispatcher to call the Worker. |
| `KOREANPULSE_LICENSE_KEY` | **yes** | Issued by Lemon Squeezy on subscription (`kp_…`). |
| `KOREANPULSE_CACHE_URL` | optional | Default `https://cache.koreanpulse.dev`. Override only for self-hosted/preview Workers. |

DART traffic always stays in your process — only translation/summary
calls leave your machine, and only to our Worker, never directly to
OpenAI. The watchlist polling that will power your Discord/Telegram
alerts (Q3 2026) is designed to run on Cloudflare Workers, not in your
local MCP process — so even when polling ships, your local MCP doesn't
become a long-running process.

## 3. Edit `claude_desktop_config.json`

Locations:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### OSS self-host config

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

### Cloud config (Solo / Analyst / Desk)

```json
{
  "mcpServers": {
    "koreanpulse": {
      "command": "koreanpulse",
      "env": {
        "DART_API_KEY": "your-dart-key-here",
        "KOREANPULSE_CACHE_MODE": "hosted",
        "KOREANPULSE_LICENSE_KEY": "kp_..."
      }
    }
  }
}
```

If `koreanpulse` isn't on PATH, use the absolute Python path:

```json
{
  "mcpServers": {
    "koreanpulse": {
      "command": "/full/path/to/python",
      "args": ["-m", "koreanpulse.server"],
      "env": {"DART_API_KEY": "..."}
    }
  }
}
```

## 4. Restart Claude Desktop

After restart you should see `koreanpulse` in the MCP tools list with six
tools:

- `track_korean_filings`
- `lookup_corp_code`
- `resolve_stock_code`
- `search_korean_industry_news`
- `monitor_activist_investors`
- `koreanpulse_about`

## 5. Try it

Open a Claude conversation and ask:

> Use koreanpulse to find Samsung Electronics in DART and show me their last 7 days of filings, translated to English.

Claude should call `lookup_corp_code('삼성전자')` →
`track_korean_filings(corp_code=..., translate=true)`.

For activist watching:

> Use koreanpulse to show me KCGI / Align Partners 5%-rule filings in the last 14 days.

Claude should call `monitor_activist_investors(days=14, activist_only=true)`.

## Failure modes

| Symptom | Likely cause |
|---|---|
| `RuntimeError: [koreanpulse:missing] Missing license key` | Tool called without `license_key` arg while `KOREANPULSE_REQUIRE_LICENSE=1`. Pass the key as a tool arg or unset the var in dev. |
| `TranslationError: KOREANPULSE_LICENSE_KEY missing` | `KOREANPULSE_CACHE_MODE=hosted` but no license key set. Either subscribe and set the key, or switch to `KOREANPULSE_CACHE_MODE=local`. |
| `TranslationError: hosted cache failed (402)` | License invalid / inactive / quota exceeded. Check your subscription dashboard. The translator does **not** silently fall back to OSS self-host mode on Worker failure — paid value stays visible. |
| `DartDailyQuotaExceeded` | Soft cap (32K/day = 80% of DART's 40K) hit. Wait until KST midnight rollover or override `DART_DAILY_QUOTA` if you have a higher allotment. |

## Cursor / other clients

Same pattern, different config file location. See
<https://modelcontextprotocol.io/docs> for client list.
