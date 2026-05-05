# MCP Market listing copy

https://mcpmarket.com — newer, growing marketplace.

## Submission
1. Public repo prerequisite
2. Visit https://mcpmarket.com → submit
3. They typically ask for: name, repo URL, description, install command,
   tags, env vars, screenshot

## Name
koreanpulse

## Description (1-2 sentences)
Get pinged in English the moment a 5%-rule filing or DART event hits a
KRX stock you care about — foreign-holder flows, activist filings, and
Korean industry news routed to your Discord / Telegram / inbox. Free
public daily snapshot at koreanpulse.dev/today; Cloud Solo $29/mo,
Analyst $79/mo, Desk $249/mo. OSS self-host available.

## Install command
```
pip install koreanpulse
```

## Required env
- `DART_API_KEY` — free at https://opendart.fss.or.kr/

## Optional env (OSS self-host / local mode, the default)
- `OPENAI_API_KEY` — server-side translation (default provider, gpt-5-mini)
- `ANTHROPIC_API_KEY` — alternative translation provider
- `KOREANPULSE_TRANSLATE_PROVIDER` — `openai` (default) | `anthropic`

## Optional env (Cloud mode for Solo / Analyst / Desk subscribers — no own provider key needed)
- `KOREANPULSE_CACHE_MODE` — set to `hosted` to call our Cloudflare Worker
  cache instead of OpenAI directly
- `KOREANPULSE_LICENSE_KEY` — required for Cloud mode (issued by Lemon
  Squeezy on subscription)

## Optional env (production)
- `KOREANPULSE_REQUIRE_LICENSE` — set to `1` to enforce license keys
- `DATABASE_URL` — required when `KOREANPULSE_REQUIRE_LICENSE=1`; Postgres
  DSN shared with the Lemon Squeezy webhook

## Categories
finance, news, search

## Tags
korea, dart, hedge-fund, kospi, kosdaq, research, industry, english,
activist, foreign-flow, diaspora, translation

## Free public demo (no install required)
https://koreanpulse.dev/today — daily snapshot updated KST 16:30 weekdays.
Foreign-holder filings, activist filings, major DART disclosures, all
summarised in English. Machine-readable JSON at
https://koreanpulse.dev/today.json (versioned schema).

## Screenshot
Demo GIF placeholder — 30s of Claude Desktop calling
`monitor_activist_investors` with `activist_only=true` for the last
14 days, displaying KCGI / Align / ValueAct / Elliott / BlackRock /
Norges filings with translated titles and summaries.

## Pricing notes
- OSS self-host: AGPL source, your own DART + OpenAI keys, community
  support only. Not a pricing tier; a separate lane for hackers.
- Public Free web: koreanpulse.dev/today (no key, no signup, no MCP, no
  alerts) — SEO + funnel surface.
- Cloud Solo $29/mo — 5 watchlists, ~2,000 queries, 30-day archive, 1 Discord/Telegram channel
- Cloud Analyst $79/mo — 25 watchlists, ~15,000 queries, 1-year archive, multi-channel alerts, CSV/JSON export
- Cloud Desk $249/mo — 3 seats, shared watchlists, ~100,000 queries, Slack/webhook alerts, team archive
- Enterprise / SLA: contact us (no published price)
- Source AGPL, hosted service commercial

## Audience anchor (multi-source verified)
KRX itself, ASIFMA, Wellington, Aberdeen, and Matthews Asia all on record
that Korean disclosure flow into English is structurally inadequate.
koreanpulse anchors on that gap. Audiences served:

- Foreign fund analysts (boutique / SMB) covering Korea
- Crypto-native rotators into KOSPI / KOSDAQ
- Korean diaspora / overseas Korean investors
- EM journalists writing English coverage
- MCP / agent developers building Korea-aware automation
