# PulseMCP listing copy

PulseMCP is hand-reviewed. Higher quality bar but better discovery.
Submit at https://www.pulsemcp.com/submit or whatever path their site uses.

## Server name
koreanpulse

## One-line summary
Get pinged in English the moment a 5%-rule filing or DART event hits a
KRX stock you care about — foreign-holder flows, activist filings,
industry news routed to your Discord / Telegram / inbox.

## Long description
There is no Bloomberg-equivalent for Korean primary sources at indie pricing.
The English-IR gap is structurally documented — KRX itself, ASIFMA,
Wellington, Aberdeen, and Matthews Asia have all gone on record that Korean
disclosure flow into English is inadequate. Foreign analysts covering Korea
either pay $24K/yr for Bloomberg's shallow Korean coverage, hire bilingual
interns, or simply miss the signal.

koreanpulse closes that gap with a watchlist-to-alert workflow on two
surfaces:

1. A free public daily snapshot at **koreanpulse.dev/today** — foreign-holder
   5%-rule disclosures (BlackRock / Vanguard / Norges / GIC / Temasek),
   Korean activist filings (KCGI / Align / ValueAct / Elliott), and major
   DART disclosures, summarised in English. Updated KST 16:30 weekdays. No
   login, no API key, machine-readable JSON at `/today.json`. Treat it as a
   preview of the daily digest paying customers get pushed to their channel.

2. Cloud subscribers get the actual workflow: give us your KRX tickers, we
   ping you in English when something material moves. The MCP server is the
   plumbing — your agent in Claude Desktop / Cursor / any MCP client can
   query the same cached, classified Korean data layer for ad-hoc research,
   and the cron-driven watchlist polling fires Discord / Telegram / Slack /
   email alerts in the background.

Seven MCP tools today (`track_korean_filings`,
`monitor_activist_investors`, `monitor_foreign_holders`, `lookup_corp_code`,
`resolve_stock_code`, `search_korean_industry_news`, `koreanpulse_about`).
Roadmap adds analyst-report digest, M&A pipeline, and Korean
earnings-call summarization.

Workflow-priced ladder:
- **Cloud Solo $29/mo** — 5 watchlists, ~2,000 queries/mo, 30-day archive,
  1 Discord/Telegram channel, daily English digest. No OpenAI key required.
- **Cloud Analyst $79/mo** — 25 watchlists, ~15,000 queries/mo, 1-year
  archive search, multi-channel alerts (Discord / Telegram / Email),
  saved searches, CSV/JSON export, priority cache + priority refresh.
- **Cloud Desk $249/mo** — 3 seats, shared watchlists, ~100,000 queries/mo,
  Slack / webhook alerts, team archive, priority support.
- **OSS self-host** — AGPL source, your own DART + OpenAI keys, community
  support only. Not a pricing tier; a separate lane for hackers.

Enterprise / SLA available on request — no published price.

## Why it's different
- **Audience-anchored on a verified gap.** The English-IR shortfall has
  multi-source institutional confirmation; we don't have to manufacture
  demand.
- **Two surfaces, one data layer.** The free `/today` snapshot funnels
  retail traffic; the paid MCP serves agent / research workflows. Neither
  cannibalises the other.
- **Cache-first economics.** Same query from any tenant hits cache;
  70% hit rate sustains ~9,500 MAU on a single DART key. Cloud
  subscribers get a global Cloudflare KV cache so cross-tenant reuse
  drives margin.
- **Foreign capital allowlist.** 20 named global asset managers / SWFs
  (BlackRock, Vanguard, State Street, Fidelity, Capital Group, T. Rowe
  Price, Wellington, Matthews Asia, Templeton, Aberdeen, Schroders,
  Norges Bank, GIC, Temasek, Goldman Sachs, JPMorgan, Morgan Stanley,
  Citadel, Millennium, Bridgewater) — their 5%-rule filings are a
  leading indicator of foreign money entering or exiting a Korean ticker.
- **Built by an operator.** Same author runs a production Korean
  automated trading system; the patterns shipped here are extracted
  from it.
- **Provider-agnostic translation.** OpenAI GPT-5-mini default
  ($0.25/M in), Anthropic Claude Haiku 4.5 fallback. Switch via env.
- **AGPL source + commercial hosted service.** Indie-friendly licensing,
  transparent codebase.

## Audience
Foreign fund analysts (boutique / SMB), crypto-native rotators into
KOSPI/KOSDAQ, Korean diaspora investors, EM journalists, MCP / agent
developers building Korea-aware automation.

## Languages supported
Korean (primary sources) → English (translation/summary)

## Pricing tiers
Cloud Solo $29/mo / Cloud Analyst $79/mo / Cloud Desk $249/mo. OSS self-host available separately for hackers (AGPL, BYO keys, community support only — not a pricing tier). Enterprise / SLA: contact us.

## Author / contact
- Author: whdrn
- Repo: https://github.com/whdrnr2583-cmd/koreanpulse
- Issues: same repo
- Email: support@koreanpulse.dev (set up before submission)

## Tags
korea, finance, dart, hedge-fund, kospi, kosdaq, research, industry,
korean-primary-sources, translation, fastmcp, activist, foreign-flow,
diaspora
