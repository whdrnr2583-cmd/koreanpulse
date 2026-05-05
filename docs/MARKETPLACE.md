# Marketplace listing checklist

Five marketplaces, one repo. Each listing's exact copy lives in `docs/listings/`.

## Submission status

| Marketplace | Listing file | URL | Submitted | Live |
|---|---|---|---|---|
| Smithery | [SMITHERY.md](listings/SMITHERY.md) | https://smithery.ai | ☐ | ☐ |
| PulseMCP | [PULSEMCP.md](listings/PULSEMCP.md) | https://www.pulsemcp.com | ☐ | ☐ |
| Glama | [GLAMA.md](listings/GLAMA.md) | https://glama.ai/mcp | ☐ | ☐ |
| MCP Market | [MCPMARKET.md](listings/MCPMARKET.md) | https://mcpmarket.com | ☐ | ☐ |
| Awesome MCP (GH) | [AWESOME_MCP.md](listings/AWESOME_MCP.md) | https://github.com/punkpeye/awesome-mcp-servers | ☐ | ☐ |

Tick boxes manually as you submit and as listings go live.

## Submission order (recommended)

1. **Smithery first** — auto-detects `smithery.yaml` in repo root. Once the
   file is in `main` and the repo is public, just submit the URL on their site.
2. **PulseMCP** — manual review, hand-curated. Highest signal-to-noise listing
   surface in the ecosystem (~12k servers, all reviewed).
3. **Glama** — largest by volume (~21k). Auto-imports from public repos.
4. **MCP Market** — newer, growing. Submit URL.
5. **Awesome MCP** (GitHub) — open a PR adding your row to README.md.

## Pre-submission checklist

Before clicking submit on any marketplace:

- [ ] Repo is public on GitHub
- [ ] README.md leads with the value prop (not the install instructions)
- [ ] `smithery.yaml` is in repo root with all required env vars documented
- [ ] PyPI package is published (`pip install koreanpulse` works)
- [ ] At least one short demo GIF or screenshot saved to `docs/assets/`
- [ ] Domain `koreanpulse.dev` resolves (even if just a single landing page)
- [ ] License (AGPL-3.0) and pricing page reachable from README
- [ ] DART quota math + capacity claims documented (`SPEC.md`)
- [ ] At least 3 tests pass live against real DART

## Logo / icon

Need:
- 256×256 PNG, transparent background, on-brand
- Hosted at `https://koreanpulse.dev/icon.png` (referenced in `smithery.yaml`)

Can ship a placeholder — most marketplaces will let you update later.

## Demo GIF

Strongly recommended. 30-60 seconds of:
1. Open Claude Desktop with koreanpulse configured
2. Ask "What did Samsung file with DART last week?"
3. Watch Claude call `lookup_corp_code` → `track_korean_filings` → translated results
4. End with the cost ledger snapshot

Tools: `peek` (Linux), `gifski`, or just Loom export.

## After submission

Track first-week metrics:
- Marketplace page views (most surface this)
- Install / signup count
- Public Free / OSS self-host → Cloud Solo / Analyst / Desk conversion (see `BETA.md` measurement framework)

Three weeks of zero conversion across all five = audience-form mismatch
signal, fall through to the BETA.md pivot ladder.
