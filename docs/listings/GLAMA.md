# Glama listing copy

Glama is the largest by volume (~21k servers). Auto-imports from public GitHub.

## Submission
1. Make repo public
2. Visit https://glama.ai/mcp/servers
3. Click "Add server", paste GitHub URL
4. Glama auto-pulls README + smithery.yaml

## What Glama will show users (auto-extracted)
- Repo description (from `pyproject.toml` `description`)
- README first heading + first paragraph
- Tool list from `smithery.yaml`
- Stars / commits / last update

## Make sure these are accurate before submitting
- `pyproject.toml` description field — should reflect the workflow tilt
  ("watchlist → English alert"); verify `description` matches before
  submission
- README's first paragraph — currently leads with the workflow framing
  ("Get pinged in English the moment a 5%-rule filing or DART event hits
  a stock you care about"), the multi-source-verified English-IR gap
  (KRX / ASIFMA / Wellington), and the Cloud tier ladder
- `smithery.yaml` env vars list — DART_API_KEY, OPENAI_API_KEY,
  ANTHROPIC_API_KEY, KOREANPULSE_REQUIRE_LICENSE, KOREANPULSE_CACHE_MODE,
  KOREANPULSE_LICENSE_KEY (Cloud-mode flow). Keep this list current.
- License field in `pyproject.toml` — currently AGPL-3.0-or-later (good for
  Glama's open-source filtering)

## Optional metadata Glama lets you add manually
- **Demo URL**: https://koreanpulse.dev/today (free public snapshot doubles
  as the demo — no login required, machine-readable JSON at /today.json)
- **Demo video URL**: TBD (Loom or YouTube, after first build)
- **Pricing page**: https://koreanpulse.dev/pricing (set up first)
- **Status (alpha/beta/stable)**: alpha at launch

## Tags to apply via Glama UI
finance, korea, dart, hedge-fund, research, industry, korean, kospi,
activist, foreign-flow, translation

## Note on free vs paid
Glama lists both free and paid servers. Two free entry points to surface
prominently:

1. **OSS self-host** — AGPL source, your own DART + OpenAI keys, community
   support only. Not a pricing tier; a separate lane for hackers.
2. **Public Free daily snapshot** — `koreanpulse.dev/today`, no MCP
   client needed, no key required

Cloud tiers (workflow-priced, watchlist-to-alert):
- Cloud Solo $29/mo (5 watchlists, ~2,000 queries, 30-day archive, 1 alert channel)
- Cloud Analyst $79/mo (25 watchlists, ~15,000 queries, 1-year archive, multi-channel alerts)
- Cloud Desk $249/mo (3 seats, shared watchlists, ~100,000 queries, Slack/webhook alerts, team archive)

Enterprise / SLA: contact us.

Make the README pricing table prominent so visitors see the OSS lane and
the Cloud Solo entry first; otherwise some users will assume "paid only"
and bounce. Linking `/today` in the demo field gives Glama browsers
something to click immediately.

## Audience hint (if Glama exposes this field)
Foreign fund analysts, crypto-native rotators into KOSPI, Korean diaspora
investors, EM journalists, MCP / agent developers.
