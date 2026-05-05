# Smithery listing copy

Smithery auto-imports from `smithery.yaml` (repo root). Submission flow:

1. Repo must be public on GitHub
2. Visit https://smithery.ai → "Add server"
3. Paste the GitHub URL
4. Smithery reads `smithery.yaml`, no separate metadata form

## Display name
koreanpulse — English-first Korean Equity Intelligence

## Tagline (≤ 80 chars)
DART filings, foreign-holder flows, Korean industry news — translated to English.

## Description (≤ 500 chars)
Get pinged in English the moment a 5%-rule filing or DART event hits a
KRX stock you care about. Foreign 5%-rule flows (BlackRock / Vanguard /
Norges / GIC / Temasek), Korean activist filings (KCGI / Align / ValueAct
/ Elliott), industry news — all watchlist-routed to your Discord /
Telegram. KRX, ASIFMA, Wellington on record: English IR flow is
structurally inadequate. Cloud Solo $29/mo, Analyst $79/mo, Desk
$249/mo. OSS self-host available.

## Tags
korea, finance, hedge-fund, dart, kospi, kosdaq, research, industry, english,
translation, korean, activist, foreign-flow

## Categories
finance, productivity, search

## Quick install (shown to users)
```bash
pip install koreanpulse
```

Then in Claude Desktop config:
```json
{
  "mcpServers": {
    "koreanpulse": {
      "command": "koreanpulse",
      "env": {
        "DART_API_KEY": "your-dart-key",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

For Cloud subscribers (Solo / Analyst / Desk — no own OpenAI key needed):
```json
"env": {
  "DART_API_KEY": "...",
  "KOREANPULSE_CACHE_MODE": "hosted",
  "KOREANPULSE_LICENSE_KEY": "kp_..."
}
```

## Tool list (auto-pulled, but write them anyway for manual review)
- `track_korean_filings` — DART filings real-time + EN translation
- `monitor_activist_investors` — DART type-D auto-tagged for KCGI / Align /
  Truston / Anda / Cha / VIP / ValueAct / Elliott + foreign passive holders
  (BlackRock / Vanguard / Norges / GIC / Temasek / Goldman / JPM)
- `lookup_corp_code` — Korean company name → DART corp code
- `resolve_stock_code` — KRX 6-digit → DART corp entry
- `search_korean_industry_news` — Korean RSS, 16 industry tags
- `koreanpulse_about` — server info / available tools

## Demo prompt (for Smithery's "try it" feature, if available)
> "Use koreanpulse to find Samsung Electronics in DART, then show me their
> last 7 days of filings translated to English."

Or for activist watching:
> "Use koreanpulse to show me which global funds (BlackRock, Norges, Elliott)
> filed 5%-rule disclosures on KOSPI tickers in the last 14 days."

## What to write in the "Why pick this server?" box
The English-IR gap is multi-source verified — KRX, ASIFMA, Wellington,
Aberdeen, and Matthews Asia all on record that Korean disclosure flow into
English is structurally inadequate. We anchor on that gap. Built by an
operator running a production Korean trading system, not a hobby wrap.
Cache-aware design — DART 40K/day budget supports ~9,500 MAU at 70% cache hit.
Free public daily web snapshot at /today (no login, no key) doubles as a
funnel front door. AGPL source, commercial hosted service.

## Audience
Foreign fund analysts (boutique / SMB), crypto-native rotators into KOSPI,
Korean diaspora investors, EM journalists, MCP / agent developers.
