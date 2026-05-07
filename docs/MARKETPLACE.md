# Marketplace listing checklist

One repo, multiple listing surfaces. Each listing's exact copy lives in `docs/listings/`.

## Submission status (verified 2026-05-07)

| # | Marketplace / surface | Listing file | URL | Submitted | Live |
|---|---|---|---|---|---|
| 1 | **Smithery** | [SMITHERY.md](listings/SMITHERY.md) | https://smithery.ai/servers/whdrnr2583/koreanpulse | ☑ | ☑ remote=true, 7 tools, description PATCH applied |
| 2 | **Glama** | [GLAMA.md](listings/GLAMA.md) | https://glama.ai/mcp/servers/whdrnr2583-cmd/koreanpulse | ☑ (auto-discovered) | ☑ score badge live |
| 3 | **MCP Market** | [MCPMARKET.md](listings/MCPMARKET.md) | https://mcpmarket.com/ko/server/koreanpulse | ☑ (auto-discovered) | ☑ AI-generated description |
| 4 | **mcp.so** | — | https://mcp.so/server/koreanpulse | ☑ (manual submit) | ☑ all 4 axes in metadata |
| 5 | **MCP Registry** (Anthropic official) | — | https://registry.modelcontextprotocol.io/v0.1/servers?search=koreanpulse | ☑ (`mcp-publisher publish`) | ☑ active, isLatest |
| 6 | **PulseMCP** | [PULSEMCP.md](listings/PULSEMCP.md) | https://www.pulsemcp.com | ☐ | ☐ |
| 7 | **punkpeye/awesome-mcp-servers** PR | [AWESOME_MCP.md](listings/AWESOME_MCP.md) | [PR #5893](https://github.com/punkpeye/awesome-mcp-servers/pull/5893) | ☑ (Glama badge added 2026-05-07) | ☐ awaiting maintainer merge |
| 8 | **jmanhype/awesome-claude-code** PR | — | [PR #42](https://github.com/jmanhype/awesome-claude-code/pull/42) | ☑ (qodo bot resolved) | ☐ awaiting maintainer merge |

Continue.dev hub — explicitly skipped 2026-05-07 after audit (GitHub App permissions too broad for the marginal discovery value; OAuth revoked).

## Submission order (taken)

1. ✅ **Smithery** — auto-discovered then `npx @smithery/cli mcp publish` for remote registration; metadata PATCH via API key.
2. ✅ **Glama** — auto-discovered from public repo, score badge auto-issued.
3. ✅ **MCP Market** (mcpmarket.com) — auto-discovered (we never submitted, the site fetched our GitHub repo and produced a description).
4. ✅ **mcp.so** — manual submit form filled (Smithery + Glama don't auto-feed mcp.so).
5. ✅ **MCP Registry** (registry.modelcontextprotocol.io) — `mcp-publisher publish` with `server.json` (remote-only entry pointing at `mcp.koreanpulse.dev/mcp`).
6. ⏳ **PulseMCP** — manual review surface, deferred. Highest signal-to-noise listing surface in the ecosystem (~12k servers, all hand-reviewed).
7. ✅ **punkpeye/awesome-mcp-servers** — PR #5893 with Glama score badge embed.
8. ✅ **jmanhype/awesome-claude-code** — PR #42, qodo bot review resolved.

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
