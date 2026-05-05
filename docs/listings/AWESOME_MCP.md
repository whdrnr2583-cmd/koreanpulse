# Awesome MCP Servers (GitHub) listing

GitHub list at https://github.com/punkpeye/awesome-mcp-servers
(or similar — there are a few competing forks; submit to the most-starred one).

## Submission
1. Fork the repo
2. Add a new line under the appropriate category section (likely "Finance"
   or "Knowledge & Research")
3. Open a PR

## Line to add (Markdown)
```markdown
- [koreanpulse](https://github.com/whdrnr2583-cmd/koreanpulse) - Get pinged in English the moment a 5%-rule filing or DART event hits a KRX stock you care about. Foreign-holder flows (BlackRock / Vanguard / Norges / GIC / Temasek), Korean activist filings, industry news — routed to Discord / Telegram / inbox. Free public daily snapshot at [koreanpulse.dev/today](https://koreanpulse.dev/today); Cloud Solo $29/mo, Analyst $79/mo, Desk $249/mo. OSS self-host available.
```

## Category placement
Best fits in either:
- **Finance & Trading** — preferred, since Korean public-company filings
  (DART) are the primary use case.
- **Knowledge & Research** — fallback if no Finance section exists in the
  current state of the awesome list.

## PR description template
```
Add koreanpulse — English-first Korean equity intelligence MCP

Adds a new MCP server focused on Korean primary financial / industry
sources translated to English for non-Korean readers.

Why it fits:
- Public, real-time data: DART (전자공시시스템) + Korean industry RSS.
  All redistributable with attribution.
- Solves a multi-source-verified gap: KRX itself, ASIFMA, Wellington,
  Aberdeen, and Matthews Asia all on record that Korean disclosure flow
  into English is structurally inadequate.
- Two surfaces, one cache:
  - Free public daily snapshot at https://koreanpulse.dev/today
    (no login, no API key, machine-readable JSON at /today.json)
  - Paid MCP for analysts / agents inside Claude Desktop / Cursor /
    any MCP client.
- 6 tools today; activist tracking (KCGI / Align / ValueAct / Elliott)
  + foreign passive holder tracking (BlackRock / Vanguard / Norges
  / GIC / Temasek + 15 more) is unique in the MCP catalogue.
- Maintained, free tier available, AGPL source.

Audience: foreign fund analysts (boutique / SMB), crypto-native rotators
into KOSPI, Korean diaspora investors, EM journalists, MCP / agent
developers.

Repo: https://github.com/whdrnr2583-cmd/koreanpulse
PyPI: https://pypi.org/project/koreanpulse/
Demo: https://koreanpulse.dev/today
Loom / video demo: <fill before opening PR>
```

## Notes
- Awesome lists tend to favor servers that are already used / starred.
  Open the PR after at least 20 GitHub stars and one external user
  testimonial — premature submission risks "needs traction" rejection.
  The free `/today` snapshot is a low-friction way to drive stars before
  submission (visitors who like the snapshot tend to star the repo).
- If there's a "Korean" or "Asia" subsection (some awesome forks have
  this), prefer it over generic Finance.
- If the awesome list maintainer asks "what makes this different from
  generic news scrapers?" → answer: (1) DART activist + foreign-holder
  classification is unique; (2) translation is cached cross-tenant
  rather than per-user; (3) free public web demo lowers eval friction.
