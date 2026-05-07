# Docs index

Single jumping-off point for everything written about koreanpulse.

## Overview

| Doc | What it answers |
|---|---|
| [README.md](../README.md) | What is this, who pays, what does it do, how do I install |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How is it built — module-by-module + data flow |
| [SPEC.md](SPEC.md) | Personas, MVP scope, pricing rationale, capacity math, roadmap |
| [CHANGELOG.md](../CHANGELOG.md) | What shipped when, in version order |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, test conventions, commit style |

## Operations

| Doc | What it answers |
|---|---|
| [RUN_LIVE.md](RUN_LIVE.md) | How to run the MCP server against real DART |
| [CLAUDE_DESKTOP.md](CLAUDE_DESKTOP.md) | How to wire koreanpulse into Claude Desktop / Cursor |
| [POSTGRES.md](POSTGRES.md) | Production LicenseStore — Supabase / RDS schema + wiring |
| [LEMONSQUEEZY.md](LEMONSQUEEZY.md) | 🚫 **NOT IN USE** — historical Lemon Squeezy setup snapshot. LS store application was declined 2026-05-06; Polar (see root `README.md` Billing + `webhook-worker/README.md`) is our sole billing provider. |
| [CI.md](CI.md) | GitHub Actions workflows, PyPI trusted publishing, cutting a release |

## Marketing & launch

| Doc | What it answers |
|---|---|
| [BETA.md](BETA.md) | 50-user-in-30-days plan + crypto-native acquisition channels |
| [DEMO.md](DEMO.md) | 60-second Loom recording script |
| [MARKETPLACE.md](MARKETPLACE.md) | Submission checklist for the 5 MCP marketplaces |
| [listings/SMITHERY.md](listings/SMITHERY.md) | Smithery-specific copy |
| [listings/PULSEMCP.md](listings/PULSEMCP.md) | PulseMCP-specific copy |
| [listings/GLAMA.md](listings/GLAMA.md) | Glama-specific copy |
| [listings/MCPMARKET.md](listings/MCPMARKET.md) | MCP Market copy |
| [listings/AWESOME_MCP.md](listings/AWESOME_MCP.md) | Awesome MCP GitHub PR template |

## Brand

| Doc | What it answers |
|---|---|
| [assets/README.md](assets/README.md) | Logo / favicon SVG sources + PNG generation |

## Code-level docstrings

The `src/koreanpulse/` modules each have a top-of-file docstring explaining
what they do and why they exist. Read those alongside `ARCHITECTURE.md`:

- `cache.py` — TTL-aware file cache + Protocol
- `corp_code.py` — DART corp index download / parse / lookup
- `dart.py` — DART OpenAPI client + `list_filings_cached`
- `news.py` — Korean industry RSS aggregator + 16-tag classifier
- `translate.py` — OpenAI / Anthropic translation with cost tracking
- `license.py` — Plan / License / InMemoryLicenseStore + validation
- `license_postgres.py` — Postgres-backed store
- `activists.py` — Korean activist allowlist + matcher
- `alerts.py` — Discord / Slack / Telegram webhook delivery
- `models.py` — Pydantic public types (Filing, Article, ActivistFiling)
- `sources.py` — RSS / DART source registry
- `server.py` — FastMCP wire-up (the 6 tools)
- `_env.py` — `.env` autoloader
- `billing/lemonsqueezy.py` — historical LS webhook handler (LS not in use since 2026-05-06; retained as reference only)
- `billing/webhook_app.py` — historical FastAPI app for the legacy Lightsail webhook receiver (superseded by `webhook-worker/` Cloudflare Worker)
