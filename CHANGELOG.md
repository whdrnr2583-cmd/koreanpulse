# Changelog

## 0.1.8 — 2026-05-09 (Apps Directory pre-submission compliance)

ChatGPT Apps Directory submission readiness — meets two specific
requirements in `developers.openai.com/apps-sdk/app-submission-guidelines`:

1. **Tool annotations**: every `@mcp.tool()` decorator now declares
   `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.
   All 7 tools are read-only and non-destructive. `openWorldHint=True`
   on the tools that touch DART / RSS endpoints; `False` on the
   in-memory lookups (`lookup_corp_code`, `resolve_stock_code`) and
   the static `koreanpulse_about` config response.

2. **Promotional language removed from docstrings**: `monitor_activist_investors`
   and `monitor_foreign_holders` previously included `**Paid tier — Solo
   $29/mo.** ... Subscribe at https://koreanpulse.dev/pricing` in the
   description. The submission guideline says "descriptions matching
   precise functionality without promotional language". Reworded to
   `**Requires a license key.** Pass it via the `license_key` argument.
   Without a valid license, this tool returns a paywall message containing
   the activation URL`. The runtime paywall string itself (returned to the
   user) still contains the Polar checkout URL — that is user-facing
   workflow text, not metadata.

Code: `src/koreanpulse/server.py` (decorators + 2 docstrings).
Tests: 181 pass, 1 skip.

## 0.1.7 — 2026-05-09 (agent-first docstrings + capability matrix)

Tool routing optimization release. The 5/8 telemetry showed Caddy POST
/mcp at 479 (200 OK) but only 3 actual `tool_call:` lines in mcp.log
over the same 10.5-hour window — agents were reaching the server,
listing tools, and then *not* calling them. The bottleneck was the
tool docstrings themselves: written for human reviewers, not for the
LLM-side retrieval / tool-selection step.

This release rewrites all 7 tool docstrings to lead with a
capability-statement first line and a `Use this tool when...`
trigger-pattern paragraph dense with the keywords agents actually see
in user queries (KOSPI / KOSDAQ / KRX / DART / 5%-rule / KCGI /
BlackRock / Norges / GIC / Samsung / Hyundai / NAVER / Kakao / 셀트리온
/ 한국경제 / 전자신문 / etc.).

The `koreanpulse_about` response also gains four new fields aimed at
agent-side capability discovery:
- `capability_tags` (15 tags — kospi, kosdaq, dart-filings, 5-percent-rule, ...)
- `supported_query_patterns` (10 patterns LLMs can match against user prompts)
- `primary_sources` (canonical source list)
- `endpoint` + `transport` (so an agent can ingest connection metadata
  in a single fetch instead of guessing from the URL)

Code:
- `src/koreanpulse/server.py`: 7 docstrings rewritten, `koreanpulse_about`
  return dict extended.

Docs:
- `README.md`: new "What this server answers (capability vector for
  agent retrieval)" paragraph after the Claude.ai/ChatGPT callout —
  same keyword set as the docstrings, so an LLM crawling the README
  for indexing sees the same surface as an agent calling
  `koreanpulse_about`.

Out of scope (deliberately):
- No new tools, no new arguments, no new pricing tier — PMF gate.
- Marketplace metadata (Smithery API description, mcp.so listing) is
  PATCHed separately at deploy time, not version-bumped.

Tests: 181 pass, 1 skipped — same as 0.1.6 (no test depended on
docstring text or about-response shape).

## 0.1.5 — 2026-05-07 (LS rejected, not dormant — verbiage correction)

Doc-only release that re-syncs the PyPI long_description with the
post-correction README. The 0.1.4 long_description still described Lemon
Squeezy as "kept dormant for future re-application" — wording the
operator (correctly) flagged as hedging away from the actual fact:
their store application was **declined** on 2026-05-06 and we did not
appeal. Polar is our sole billing provider, full stop. The previous
softer phrasing risked LLM crawlers (Glama / mcpmarket) and human
prospects classifying LS as "another option on the table" instead of
"closed path."

Code: no changes. The 0.1.4 server runtime is identical to 0.1.5.

Docs:
- README §Billing: "Lemon Squeezy: dormant" → "Lemon Squeezy: not in
  use. Their store application was declined on 2026-05-06; we did not
  appeal." Three other paragraphs in the section parallelled the same
  hedge → all switched to declined / sole / historical-reference
  language.
- `docs/LEMONSQUEEZY.md` top banner: 🚧 DORMANT → 🚫 NOT IN USE.
  Removes "we can flip back once subscription count justifies a
  re-application" — the most directly misleading sentence on the repo.
- `webhook-worker/README.md`: lead paragraph + every reactivation
  reference rewritten. Legal-posture section now states explicitly
  "We have no MoR relationship with Lemon Squeezy." LS comment block
  in the secrets section says "any LS traffic in production is by
  definition spurious".
- `webhook-worker/wrangler.toml`: LEMONSQUEEZY_* secret comment block
  changed from "(dormant — application denied; kept for future re-
  application)" to "NOT IN USE — Polar is sole MoR. Do NOT set in
  production."
- `docs/ARCHITECTURE.md`: ASCII MoR box + process table both updated.
- `docs/SPEC.md`, `docs/DEMO.md`, `docs/BETA.md`,
  `docs/listings/MCPMARKET.md`: same swap in their billing-related
  cells.

The 0.1.4 entry below remains accurate for the runtime/code changes
that shipped that day; this release is purely the verbiage correction
on top.

## 0.1.4 — 2026-05-07 (positioning + paywall + LS dormant verbiage)

PyPI release that re-syncs the package long-description with the post-Polar
README. The 0.1.3 publish predated the Lemon Squeezy → Polar pivot, so
`pypi.org/project/koreanpulse/0.1.3/` rendered LS as the active billing
provider — confusing for prospects who arrived via PyPI search instead of
landing or Smithery. 0.1.4 ships the corrected README + supporting cleanups.

Code:
- `_paid_gate` returns `Optional[str]` instead of raising `RuntimeError`.
  Paywall reaches the user as a normal tool result (`isError=False`), so
  ChatGPT / Claude.ai connector clients hand the subscribe URL straight to
  the user instead of treating it as an internal failure (`adc5ac8`).
- `monitor_activist_investors` and `monitor_foreign_holders` now return
  `list[Model] | str` so the schema matches the runtime behaviour.
- Replaced the dead Polar fallback URL (`polar_cl_dopobJ…`, 302→polar.sh
  homepage) embedded in four tool docstrings with the canonical
  `koreanpulse.dev/pricing` redirect (`50448a4`).

Docs / positioning:
- README: explicit `## Billing (Polar — active provider)` heading with a
  block stating LS is dormant and that any LS reference below the section
  is documentation-only. Replaces the soft "kept dormant for future
  re-application" wording that auto-fetchers (Glama, mcpmarket) were
  catching as an active-provider signal.
- `docs/LEMONSQUEEZY.md`: top-of-file 🚧 DORMANT banner so the file is
  read as historical reference even when discovered out of context.
- `docs/MARKETPLACE.md`: refresh from a 5-row to-do checklist into an
  8-row submission status table reflecting Smithery / Glama / MCP Market
  / mcp.so / MCP Registry / PyPI / punkpeye-PR / awesome-claude-code-PR.
- `docs/listings/MCPMARKET.md`: record the auto-discovery (the manual
  submit form returned "이미 등록되어 있습니다").

Distribution:
- Submitted to MCP Registry (`registry.modelcontextprotocol.io`) via
  `mcp-publisher publish`. server.json description hard-capped at 92
  chars to satisfy registry validation.
- Submitted to mcp.so manually with full metadata + Server Config JSON.
- Smithery republished + description PATCH applied twice (positioning
  refresh after the competitor audit added "for ChatGPT / Claude.ai" +
  N→1 multi-user framing).
- punkpeye/awesome-mcp-servers PR #5893: Glama score badge committed to
  the head branch so the glama-check bot stops blocking.
- Skipped Continue.dev hub after permission audit (GitHub App scope too
  broad for marginal discovery; OAuth revoked).

Landing:
- New hero eyebrow + sub-paragraph naming the 1-click connector URL
  (`mcp.koreanpulse.dev/mcp`) and the N→1 hosted scaling story
  (~9,500 MAU on a single DART key at 70% cache hit).
- New "How koreanpulse compares" section with a four-column matrix vs
  korea-stock-mcp / korean-dart-mcp / openregistry, including honest
  out-of-scope rows (KRX OHLCV, XBRL, HWP/PDF) so the wrong-fit user
  is steered to the right server.
- `/pricing` route added so the paywall message URL stops 404'ing
  (`e4d8172`).
- Vercel Web Analytics enabled; Caddy access log activated on
  mcp.koreanpulse.dev so external traffic can finally be attributed to
  ChatGPT (`openai-mcp/1.0.0`) vs Claude.ai (Cloudflare DC OAuth path).



All notable changes to koreanpulse, in version order. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely.

## [Unreleased]

Building toward `v0.2.0`. The `v0.1.0` first PyPI release shipped 2026-05-05.

### Legal infrastructure (2026-05-05 evening)

Same-day audit + auto-implementation of regulatory mitigations before any payment is received.

**Live (deployed to koreanpulse.dev)**:
- `/privacy` — Privacy Policy covering Korea PIPA, EU GDPR, US CCPA. Collection items, lawful basis (per data type), retention periods (waitlist 24mo, paid records 5yr per Korean tax law, logs 30d), sub-processor list (Lemon Squeezy / Cloudflare / Vercel / OpenAI), data subject rights, breach notification within 72h, CPO contact (`privacy@koreanpulse.dev`).
- `/terms` — Terms of Service. "Not investment advice" callout in Korean and English, AGPL vs hosted-data IP split, 30-day refund (Lemon Squeezy MoR), Korean Capital Markets Act §101 acceptable-use clause, Seoul Central District Court venue.
- Landing footer: Privacy + Terms links visible on every page.
- Landing form: required consent checkbox; submit button disabled until consent given (GDPR + PIPA opt-in compliance).
- Landing body: dedicated "Not investment advice" disclaimer block, both Korean and English.
- README §Legal posture: explicit citation of §101 self-classification ("단순 금융 관련 지식 제공"), pointers to /privacy and /terms.

**Reference document**: `_workspace/legal_audit_2026-05-05.md` — full risk matrix, mitigation copy templates, Korean PIPA §30 required items, US Investment Advisers Act §202(a)(11)(D) publisher-exception three-prong test (Lowe v. SEC, 1985).

**Pending user action** (cannot be automated):
- Korean business registration (홈택스 → 간이과세자, ~30 minutes online) immediately before first payment.
- `privacy@koreanpulse.dev` and `legal@koreanpulse.dev` email aliases (Cloudflare Email Routing or Gmail forwarding).
- Optional: 1-hour consultation with a Korean Capital Markets Act lawyer (~₩200,000) after the first 5 paid signups, to validate the §101 self-classification and Korean news fair-use posture in writing.

**Pending git push**: commit `e72a565` is committed locally but not pushed — the PAT was revoked end-of-day. Next session, after a fresh PAT (with `repo` + ideally `workflow` scope), `git push` will sync this and any subsequent commits.



## [v0.1.0] — 2026-05-05

First public release. End of bootstrap; start of beta acquisition.

### Released

- **PyPI**: `koreanpulse 0.1.0` (https://pypi.org/project/koreanpulse/0.1.0/)
- **PyPI**: `agentprod 0.0.1` (https://pypi.org/project/agentprod/0.0.1/) — separate repo, MIT, required dep
- **GitHub**: public repo at `https://github.com/whdrnr2583-cmd/koreanpulse` (AGPL-3.0)
- **Production**: domain `koreanpulse.dev` registered + 4 surfaces live —
  `/` (Vercel landing), `/today` + `/today.json` + `/today/{date}` (daily-worker
  via Cloudflare route), `cache.koreanpulse.dev` (cache-worker), `api.koreanpulse.dev`
  (webhook-worker, Lemon Squeezy + license validate)
- **Smithery**: `whdrnr2583/koreanpulse` published with hosted HTTP gateway at
  `koreanpulse--whdrnr2583.run.tools` — closes the "true HTTP-transport remote
  MCP, no `pip install`" gap that was originally a Q3 2026 ship target
- **Awesome MCP**: PR #5893 open with 🤖🤖🤖 fast-track marker
- **Glama**: server submitted, pending hand-review
- **PulseMCP**: submission email sent to hello@pulsemcp.com (weekly ingest cycle)
- **Lemon Squeezy**: 4 variants registered (Solo $29 / Analyst $79 / Desk $249 /
  Lifetime $299 private). Application under merchant review with Shahan@LS;
  follow-up requested overview / pricing / demo, replied 2026-05-05
- **D1 license database**: `0001_licenses.sql` + `0002_pricing_v2.sql` migrations
  applied to remote
- **Cloudflare secrets**: 6 in webhook-worker, 2 in cache-worker, 3 in
  daily-worker — all rotated to fresh OpenAI key (the original key was 401)

### Reconciled

- **Copy ↔ code mismatch fixed**: README + HN_LAUNCH no longer claim "true
  HTTP-transport remote MCP is Q3 2026 ship target" — Smithery hosted gateway
  delivers it today. Watchlist polling + alert dispatch + per-tier limit
  enforcement remain Q3 2026 (unchanged, real ship target).
- **Distribution / marketplaces section** in README updated with live URLs
  for Smithery, Glama, PulseMCP, Awesome PR, MCP Market.

### Verified end-to-end

- LS webhook synthesised flow (subscription_created → license issued → /v1/validate
  → KV translation → subscription_cancelled → license inactive) all 7 cases pass
- cache-worker /v1/translate against real OpenAI: translate ✓, summarize ✓, KV
  cache hit ✓, bad license rejected with 402 ✓
- daily-worker /today.json + /today HTML + /today/{date} archive all 200, route
  patterns at `koreanpulse.dev/today` (exact) + `/today/*` + `/today.json`
- `pip install koreanpulse` resolves via PyPI (agentprod auto-pulled as transitive)

### Pending — next session

- Demo video (Loom, 60-90 sec) — for LS Shahan follow-up by 2026-05-12
- Daily cron monitoring: confirm `/today.json` `takeaway` / `activist_filings`
  / `foreign_flows` populated post OpenAI key rotation (next cron 2026-05-06
  UTC 07:30)
- Multiplier DM (Sanghyun Park / Douglas Kim) Wed–Thu 09:00–11:00 KST
- Show HN: gated on 3 consecutive successful cron builds — earliest viable
  date 2026-05-12 or 2026-05-13 (Tue/Wed)
- GitHub PAT + PyPI token revoke (channel-exposed; both single-use)



### Pre-domain-registration consistency sweep (2026-05-05 round 4)

Final doc-consistency pass before the user registers `koreanpulse.dev`.
The user-facing checklist that drives the next 14 days of operator work
(`_workspace/checklist_ko_2026-05-05.md`) had four small but operator-
breaking errors plus a few stale references in adjacent operator docs.
Fixed:

- **`checklist_ko_2026-05-05.md` §2-3 D1 deploy commands** — the
  database name (`koreanpulse_db`, not `koreanpulse`), the secret name
  (`KOREANPULSE_CACHE_SHARED_SECRET`, not `CACHE_SHARED_SECRET`), the
  migration command (`npm run migrate:prod`, which now also runs
  `0002_pricing_v2.sql`), and the variant-secret list (`SOLO` /
  `ANALYST` / `DESK` + `LIFETIME`, with the deprecated
  `PRO`/`STARTER`/`INDIE`/`ENTERPRISE` slots called out as
  "leave unset in production"). Without this fix, an operator who
  followed the checklist verbatim would deploy an empty schema and a
  Worker that couldn't talk to the cache layer.
- **`checklist_ko_2026-05-05.md` §1-2 LS variant guidance** — the
  Design Partner Lifetime variant must exist in LS so the webhook can
  resolve it, but it must be **hidden from the storefront**
  (Settings → Storefront → Hide variant). Annual variants demoted to
  "post-launch" — monthly-only at v0 keeps the LS setup tight (3
  variants instead of 6).
- **`checklist_ko_2026-05-05.md` §8 automation table** — "Pro/Lifetime
  결제 즉시 라이선스 발급" → "Cloud Solo/Analyst/Desk + Lifetime SKU
  결제 즉시 라이선스 발급". Aligns the automation summary with the
  pricing-v2 ladder.
- **`docs/LEMONSQUEEZY.md`** — top-of-file banner pointing operators at
  `webhook-worker/README.md` for the deploy path (the file's
  Render/Railway/Fly hosting guidance is now historical context for the
  *Variant + storefront* flow only). Webhook URL example updated to
  `https://api.koreanpulse.dev/webhook/lemonsqueezy`. Lifetime SKU
  re-activated in the env example as the **active** Design Partner SKU
  (was incorrectly listed as retired in round 3).
- **`docs/BETA.md` Day-0 instrumentation** — `tools_used` which-of-5 →
  which-of-7. Same as the README correction in round 3, applied to the
  beta-plan analytics field.

Code untouched in this round; 181 tests still pass. The next round of
edits is operator action — domain registration, then Cloudflare deploys.

### Operator-doc + numeric staleness fix (2026-05-05 round 3)

Codex audit round 3 caught five residual gaps after rounds 1+2 — all
narrowly about operator/marketplace-doc staleness rather than positioning.
Fixed:

- **Billing variant naming** — `README.md` Billing block + `webhook-worker/
  README.md` setup steps + Pricing-v2 section all now name the active
  variant secrets (`LEMONSQUEEZY_VARIANT_SOLO` / `_ANALYST` / `_DESK` +
  `_LIFETIME`) instead of the deprecated `_PRO`. The deprecated slot is
  still wired in code for back-compat with pre-pricing-v2 storefronts but
  is explicitly called out as "leave unset in production."
- **Migration scripts** — `webhook-worker/README.md` Schema section now
  references both `0001_licenses.sql` and `0002_pricing_v2.sql` (the
  CHECK-constraint expansion that permits `solo` / `analyst` / `desk`
  alongside the deprecated values). `npm run migrate:prod` runs both.
- **README Status line** — "5 tools shipped, 41 tests pass" was stale
  (we ship 7 and pass 181 — pricing v2 + workflow framing landed
  alongside). Now reads "7 MCP tools shipped. 181 tests pass. Beta/
  waitlist tone — watchlist polling + alert dispatch ship Q3 2026."
- **README "What it does" tool table** — was 5 rows, now 7 (adds
  `monitor_activist_investors` + `monitor_foreign_holders`, in line with
  the Pricing-v2 messaging that already names the foreign-holder feed
  in the Hero copy).
- **`SELF_HOSTING.md` "(forthcoming)" residue** — already created in
  round 2 but the README still flagged it as forthcoming. Replaced with
  a working link to `docs/SELF_HOSTING.md`.
- **Honesty marker on per-tier enforcement** — landing + README now say
  "the **only** runtime-enforced difference between tiers is the monthly
  query cap (2K / 15K / 100K)"; seat counts, watchlist counts,
  alert-channel limits, and archive-retention windows are explicitly
  marked as "paper limits until the polling/dispatch loop lands." The
  prior copy ("query cap **and** seat count") overstated current
  enforcement and is gone.

181 tests still pass; no code-side change in this round (the prior
rounds already landed the `Plan.SOLO/ANALYST/DESK` enum, variant map,
D1 migration, and tests).

### Beta/waitlist tone reconciliation (2026-05-05 round 2)

Codex audit round 2 applied. Customer-facing copy was getting ahead of
what the implementation actually ships, so we walked the tone back from
"buy today" to "beta / waitlist with lock-in launch rate" until the
watchlist polling loop + alert dispatch + true HTTP remote-MCP transport
land in Q3 2026.

- **Remote MCP claim → Hosted translation cache.** Every "Remote MCP —
  no install gymnostics" / "no install gymnastics" / "remote MCP" claim
  in customer copy was rewritten to **"Hosted translation cache (no
  OpenAI key needed)"**. The honest truth is that Cloud customers still
  install the local Python MCP (`pip install koreanpulse` + 4-line
  Claude Desktop config); switching `KOREANPULSE_CACHE_MODE=hosted`
  routes only translation calls to our Cloudflare Worker, which holds
  our OpenAI key and validates the license. A true HTTP-transport
  remote MCP (no local install at all) is on the roadmap, marked
  **Q3 2026**.
- **Watchlist + alerts marked Q3 2026.** Hero CTA changed from
  "Start a watchlist" → "Join the waitlist". A beta banner above the
  pricing table on the landing flags the trial-opens-Q3 status. Pricing
  tiers stay $29 / $79 / $249 with the framing "Lock-in pricing —
  early supporters keep the launch rate" instead of "buy today". Each
  Cloud feature in the per-tier feature list is annotated `(live today)`
  vs `(Q3 2026)` so customers can see exactly what they're paying for.
- **Plan-tier honesty disclosure.** Until the polling/dispatch /
  multi-seat / retention enforcement code lands, every customer surface
  that compares Solo / Analyst / Desk now includes a one-liner: today's
  enforced delta is the monthly query cap (2K / 15K / 100K) and seat
  count (1 / 1 / 3) only; watchlist count, alert-channel count, and
  retention are paper limits until Q3 2026. Avoids the trust hit on
  first paid customer.
- **Architecture / Billing reconciled to Cloudflare Worker + D1
  reality.** `docs/ARCHITECTURE.md` rewritten — ASCII diagram now shows
  the local MCP + Cache Worker + Webhook Worker (D1) + Daily Worker
  topology rather than the old FastAPI + Postgres on Lightsail picture.
  Module breakdown extended to cover `webhook-worker/`, `cache-worker/`,
  `daily-worker/`, `koreanpulse.alerts`. `README.md` Billing section
  rewritten to point at `webhook-worker/README.md` + `wrangler deploy`
  instead of `koreanpulse-webhook --port 8788` + `pip install
  'koreanpulse[billing]'`. The legacy Lightsail/FastAPI/Postgres path
  was moved to **`docs/legacy/POSTGRES_LIGHTSAIL.md`** (with a
  superseded-2026-05-05 header) and linked from a `## Legacy` section
  in ARCHITECTURE.md. Source modules
  (`koreanpulse.billing.webhook_app`, `koreanpulse.license_postgres`,
  `migrations/001_licenses.sql`) remain in the tree for back-compat
  but are not surfaced in customer-facing setup docs.
- **Marketplace metadata synced.** `smithery.yaml` displayName +
  description rewritten to match the landing — removed the stale
  `$19/mo` reference and the old "Korean Industry Intelligence" frame,
  added the beta-status disclosure + Solo/Analyst/Desk waitlist
  pricing + KOREANPULSE_CACHE_MODE / KOREANPULSE_LICENSE_KEY env hints.
- **HN_LAUNCH.md** body + self-comment + Q&A rewritten so the post
  reads as a waitlist launch ("queries + hosted translation are live
  now; watchlist polling + alert dispatch ship Q3 2026") rather than
  a "buy today" launch.
- **`landing/public/.well-known/mcp.json`** pricing block now carries
  `status: waitlist` + `live_today` + `ships_q3_2026` arrays per tier
  so MCP-client crawlers and AI agents reading the manifest get the
  honest implementation status programmatically.
- **`landing/public/llms.txt`** opening paragraph rewritten in beta
  tone; "Pro customer" residue replaced with "Cloud Solo customer";
  legacy Postgres setup link replaced with the webhook-worker D1 link.
- **`docs/CLAUDE_DESKTOP.md`** quick-decision table extended with the
  Q3 2026 ship-target column and an explicit note that local install
  is still required for Cloud customers today.
- **`_workspace/checklist_ko_2026-05-05.md`** prefaced with a beta-
  reconciliation banner so the operator-facing checklist reflects the
  tone shift.
- **Surfaces touched**: `landing/app/page.tsx`, `README.md`,
  `landing/public/.well-known/mcp.json`, `landing/public/llms.txt`,
  `smithery.yaml`, `docs/ARCHITECTURE.md`, `docs/HN_LAUNCH.md`,
  `docs/CLAUDE_DESKTOP.md`, `docs/SPEC.md`,
  `docs/legacy/POSTGRES_LIGHTSAIL.md` (new),
  `_workspace/checklist_ko_2026-05-05.md`.
- **Code-side notes for main Claude** (not edited here, owned by the
  parallel main-Claude track on `src/koreanpulse/license.py`,
  `src/koreanpulse/billing/lemonsqueezy.py`, `webhook-worker/src/*.ts`,
  `webhook-worker/migrations/*.sql`, `tests/test_*.py`,
  `docs/SELF_HOSTING.md`, `.env.example`):
  - `PLAN_LIMITS` keys `watchlists` / `alert_channels` / `seats` /
    `retention_days` need runtime enforcement before the public copy
    stops carrying the "Q3 2026" disclaimer.
  - The translator's `KOREANPULSE_CACHE_MODE=hosted` path is the
    primary value Cloud customers receive today; tests should keep
    validating that hosted-mode failures do **not** silently fall back
    to local (paid value stays visible).
  - Hard rules from `docs/BETA.md` remain verbatim; no relaxation.

### Pricing v2 + workflow positioning (2026-05-05)

Codex audit verdict applied. Customer-facing surfaces rewritten to lead
with the watchlist-to-alert workflow rather than the MCP tools surface,
and the previous Free/Pro $19/Lifetime $99 model collapsed into a
workflow-priced Cloud ladder + an OSS lane.

- **Pricing**:
  - **Cloud Solo $29/mo** — 5 watchlists, ~2,000 queries/mo, 30-day
    archive, 1 Discord/Telegram channel, daily English digest. No
    OpenAI key required. Floor tier for the watchlist workflow.
  - **Cloud Analyst $79/mo** — 25 watchlists, ~15,000 queries/mo, 1-year
    archive, multi-channel alerts (Discord / Telegram / Email), saved
    searches, CSV/JSON export, priority cache + priority refresh. The
    real revenue tier.
  - **Cloud Desk $249/mo** — 3 seats, shared watchlists, ~100,000
    queries/mo, Slack / webhook alerts, team archive, priority support.
    Boutique research desks.
  - **Public Free** (web only) — `/today`, `/today.json`, last-3-day
    archive, no login, no MCP, no alerts. SEO + funnel + AI-crawler
    surface, not a pricing tier.
  - **OSS self-host** — AGPL source, run the MCP locally with own
    `DART_API_KEY` + `OPENAI_API_KEY`. Community support only. No
    alerts, no hosted archive, no remote MCP, no shared cache, no
    account sync. Surfaced in README + (future) `docs/SELF_HOSTING.md`,
    **not** in the pricing table.
  - **Design Partner Lifetime $299** — private, 20-seat cap,
    contact-only. Footnote-only mention in README and one operator
    doc. Never on landing or in marketplace listings.
- **Retired**: the `Pro $19/mo` unmetered subscription and the
  `Lifetime $99 first 100` one-time SKU are removed from all
  customer-facing copy. Plan enum back-compat (`Plan.STARTER/INDIE/
  ENTERPRISE/PRO`) remains in `license.py` for grandfathered licenses;
  customer surfaces no longer reference any of them.
- **Messaging shift**: Hero rewritten across landing, README, mcp.json,
  llms.txt to lead with `Watchlist → English alert` outcome ("Get
  pinged in English the moment a 5%-rule filing or DART event hits a
  stock you care about") rather than the previous tool-led framing
  ("English-first Korean equity intelligence — 7 MCP tools…"). MCP
  tools moved below pricing on the landing page, framed as "what runs
  under the hood when you connect your AI client".
- **CTAs**: primary "Start a watchlist" (was "See today's snapshot");
  secondary "Preview the daily digest" linking to `/today` (was "View
  on GitHub"). Email capture button "Notify me when Solo trial opens".
- **Customer surfaces updated**: `landing/app/page.tsx`, `README.md`,
  `landing/public/.well-known/mcp.json`, `landing/public/llms.txt`,
  `docs/CLAUDE_DESKTOP.md`, `docs/HN_LAUNCH.md`, `docs/SPEC.md`,
  `docs/LEMONSQUEEZY.md`, `docs/MARKETPLACE.md`, `docs/BETA.md`,
  `docs/listings/{SMITHERY,PULSEMCP,GLAMA,MCPMARKET,AWESOME_MCP}.md`,
  `_workspace/checklist_ko_2026-05-05.md`,
  `_workspace/user_actions.md` (banner only).
- **Code-side TODO** (not touched in this commit, see
  `_workspace/pricing_v2_workflow_2026-05-05.md` for the list):
  `src/koreanpulse/license.py` plan enum + price/limit constants,
  `src/koreanpulse/billing/lemonsqueezy.py` variant map,
  `webhook-worker/src/*.ts` variant map + plan dispatch,
  `webhook-worker/migrations/*.sql` (new tier rows if needed),
  `.env.example` env-var keys, `tests/test_license.py`,
  `tests/test_lemonsqueezy.py`. Also: wire the
  `cache-worker`/`daily-worker` cron + `koreanpulse.alerts` into the
  watchlist polling loop that the new pricing depends on.

### Infrastructure simplification — webhook-worker on Cloudflare D1
- New `webhook-worker/` package — Cloudflare Worker + D1 (SQLite) replacing
  the Lightsail/FastAPI/Postgres webhook deployment. Operator now runs
  zero servers; whole stack is 100% Cloudflare (cache + daily +
  webhook workers, all on free tier, single dashboard).
- Two D1 tables (`migrations/0001_licenses.sql`):
  - `licenses` — mirrors the Postgres schema with SQLite-compatible
    types (TEXT timestamps, INTEGER booleans, JSON-as-TEXT metadata).
    Denormalised `is_lifetime` + `deal_seq` columns for indexable
    lifetime-deal accounting (D1 has no JSONB functional indexes).
    CHECK constraint still permits the deprecated plan strings
    (`starter`/`indie`/`enterprise`) for back-compat.
  - `webhook_events` — idempotency log (PK on `webhook_id`).
- Three TS modules (~700 LOC):
  - `src/license.ts` — D1 query helpers (`getByKey`, `findByEmail`,
    `nextLifetimeSeq`, `upsertLicense`, `incrementUsage`,
    `validateAndCharge`, `markEventSeen`, `issueLicenseKey`).
  - `src/lemonsqueezy.ts` — HMAC-SHA256 verify (constant-time),
    7-event dispatcher, role/self_description capture, idempotency
    via D1.
  - `src/index.ts` — fetch handler for `/health`, `/webhook/lemonsqueezy`,
    `/v1/validate`. Mirrors the Python webhook semantics 1:1.
- `README.md` Architecture row updated; `landing/public/llms.txt` doc
  link updated to "3 Cloudflare Workers + D1 license store".
- Free-tier budget: 100K Workers req/day + 5M D1 reads/day + 100K
  D1 writes/day — several orders of magnitude headroom for paid traffic.
- Cost saved: ~$5/month Lightsail. Ops removed: SSH, Postgres install,
  Caddy/nginx, systemd unit, env-file management.
- Migration path documented in `webhook-worker/README.md` (CSV dump
  from Postgres → D1 import). For v0 (zero production traffic yet),
  start fresh on D1.

### Pricing simplification (2026-05-05)
- Collapsed 6 tiers (Free / Starter / Indie / Pro / Enterprise / Lifetime)
  to 3 (Free / Pro / Lifetime) plus an Enterprise contact-us footnote.
  User decision: 가격대가 너무 차이나 — single mid-tier subscription, not
  enterprise-shaped, "decide whether to use it or not, no tier shopping."
- **Free** is now BYOK-unlimited (the user supplies their own OpenAI key,
  so we don't meter their calls). `calls_per_month = -1` in `PLAN_LIMITS`.
- **Pro $19/mo** is the only published paid tier. Inherits the old Indie
  feature set: hosted cache, Discord push priority, history retention,
  search. Single user license — no multi-seat. Soft cap of 50,000
  calls/mo for abuse-only rate limiting; the LS variant is unmetered in
  practice.
- **Lifetime $99** (was $149) — 100-seat cap unchanged. Price anchored to
  ~5× the new Pro monthly. Grants `Plan.PRO` (was `Plan.INDIE`).
- **Enterprise** — no published price. Surface footnote only:
  "Enterprise / SLA: contact us." Preserves optionality without cluttering.
- **Plan enum back-compat**: `Plan.STARTER`, `Plan.INDIE`, `Plan.ENTERPRISE`
  retained as deprecated aliases — `PLAN_PRICING_USD` and `PLAN_LIMITS`
  for those three now mirror Pro. Webhook handlers only exercise PRO and
  LIFETIME paths in production. `LEMONSQUEEZY_VARIANT_STARTER/INDIE/ENTERPRISE`
  env vars are accepted for back-compat but not required; only `PRO` and
  `LIFETIME` need to be set.
- Surfaces updated for consistency: `landing/app/page.tsx`, `README.md`
  (Pricing + Who pays + BYOK vs Hosted), `landing/public/.well-known/mcp.json`,
  `landing/public/llms.txt`, `docs/CLAUDE_DESKTOP.md`, `docs/HN_LAUNCH.md`,
  `docs/SPEC.md`, `docs/listings/{SMITHERY,PULSEMCP,GLAMA,MCPMARKET,AWESOME_MCP}.md`,
  `_workspace/{user_actions,checklist_ko,cold_email_targets,multiplier_outreach}*.md`,
  `.env.example`, `tests/test_license.py`, `tests/test_lemonsqueezy.py`.

### Marketing simplification

User decision: "단순하게 작업은 불가능한가? ... 적당히 괜찮은 서비스를
지속적으로 판매하는게 목적이다." Compressed the 9-channel BETA plan and
the ~700-line user-action runbook into a v0 footprint a single founder
can ship sustainably.

- **`docs/BETA.md`** — Channels 1–9 collapsed to 5: Marketplaces (passive),
  Show HN (1-shot), Multiplier DM (Park + Kim), Reddit answer-only,
  Natural SEO via `/today`. Channels 5/6/8/9 (cold email / Korean diaspora /
  Indie Hackers retro / Telegram) and the Crypto Discord cluster moved to
  a deferred list. Acquisition copy reordered: "English-first KRX
  intelligence" promoted to primary (audience-evidence verified);
  "blockchain explorer" demoted to secondary. Day-30 conversion question
  updated for 3-tier pricing (Pro $19/mo / Lifetime $99 / Neither). Hard
  rules unchanged.
- **`_workspace/checklist_ko_2026-05-05.md`** — Compressed from 604 → ~243 lines.
  Lightsail/Postgres webhook server replaced by Cloudflare D1 +
  `webhook-worker` deploy step. KIS API support inquiry section removed
  (deferred until Pro paying customers exist). Cold email Top 5 / round-2
  research and Korean diaspora references removed. Self-contained — first
  reader can ship without consulting predecessor.
- **`_workspace/deferred_channels_2026-05-05.md`** — New ~140-line memo
  cataloging cold email (14 firms), Korean diaspora forums, Indie Hackers,
  Telegram, Crypto Discord, Product Hunt. Each channel: rationale for
  deferral + specific activation trigger on top of the BETA.md
  "≥5 paid signups" hard rule. Source files (`cold_email_targets_*.md`,
  `diaspora_channels_2026-05-05.md`) preserved for activation.
- **`_workspace/user_actions.md`** — Marked superseded with banner pointing
  to the compressed checklist; kept as historical reference.

### Added
- **6 MCP tools** registered in the server:
  - `track_korean_filings` — DART filings + EN translation/summary, cached
  - `lookup_corp_code` — Korean company name → DART corp_code
  - `resolve_stock_code` — KRX 6-digit → DART corp entry
  - `search_korean_industry_news` — etnews + hankyung RSS, 16-industry classifier
  - `monitor_activist_investors` — DART type-D filings auto-tagged for known
    Korean activists (KCGI, Align, Truston, Anda, Cha, Life, Platform, VIP,
    ValueAct, Elliott)
  - `koreanpulse_about` — server metadata
- **Caching layer** (`koreanpulse.cache.FileCache`) with per-entry TTL.
  Translations cached forever; filing lists cached freshness-aware (60s for
  today, 1h for 1–6d, 24h for 7d+).
- **DART daily soft quota** (default 32 000/day = 80% of DART's 40K hard
  cap), enforced before every outbound call. KST midnight rollover.
  `DART_DAILY_QUOTA` env override.
- **Title-prefix filing-type classifier** (`_classify_filing_type`) — DART's
  `list.json` doesn't return `pblntf_ty`, so we infer A/B/C/D/E/F/G/H/I/J
  from the report title. 30+ patterns covering periodic, major-event,
  shareholding, audit, and exchange disclosures.
- **Translation provider abstraction** — OpenAI (default, GPT-5-mini) and
  Anthropic (fallback, Claude Haiku 4.5). Provider switchable via
  `KOREANPULSE_TRANSLATE_PROVIDER` env. Cost recorded per call via
  `agentprod.CostTracker` with provider + op labels.
- **Korean industry classifier** — `INDUSTRY_KEYWORDS` covers 16 industries
  (semiconductor, shipbuilding, battery, biotech, defense, auto, ev_charging,
  ai, steel, petrochem, construction, fintech, gaming, ecommerce, telco, energy).
- **Korean activist allowlist** (`koreanpulse.activists.KOREAN_ACTIVISTS`) —
  10 entries with Korean + English aliases.
- **Webhook alerts module** (`koreanpulse.alerts.send_alert`) — Discord,
  Slack, Telegram delivery. URL auto-detect, per-channel formatting,
  fire-and-forget error handling.
- **License system** — 5 plans (Free / Starter / Indie / Pro / Enterprise) +
  $149 lifetime deal (first 100). `InMemoryLicenseStore` for v0,
  `PostgresLicenseStore` for production. Postgres schema in
  `migrations/001_licenses.sql`.
- **Lemon Squeezy webhook handler** (`koreanpulse.billing`):
  - HMAC-SHA256 signature verification (constant-time compare)
  - Idempotency via `meta.webhook_id` LRU
  - Handles 7 LS event types (subscription lifecycle + order_created)
  - Lifetime licenses preserved through subscription cancellation
  - Variant ID → Plan mapping configurable via env
- **Console scripts**:
  - `koreanpulse` — MCP server (stdio)
  - `koreanpulse-webhook` — FastAPI billing endpoint
- **`.env` autoloader** (`koreanpulse._env`) — searches
  `KOREANPULSE_ENV_FILE`, cwd, repo root in order. Never overrides existing env.
- **CJK-safe stdout** — `examples/quickstart.py` reconfigures stdout to UTF-8
  on Windows so Korean prints correctly under cp949 consoles.
- **DART corp code index** — auto-downloads ~5 MB XML (117 k entries) on
  first lookup, cached on disk for 7 days.
- **Marketing assets**:
  - `docs/assets/logo.svg` (256×256 with wordmark)
  - `docs/assets/icon.svg` (64×64 mark only, for favicon)
- **Landing page** (`landing/`) — Next.js 15 + Tailwind, single-page,
  email capture, crypto-native targeted copy. Vercel-deploy ready.
- **GitHub Actions** workflows:
  - `ci.yml` — Python 3.10/3.11/3.12 matrix, pytest + ruff + sdist
  - `release.yml` — PyPI trusted publishing on `v*.*.*` tag, with version
    matching against `pyproject.toml`
- **Documentation**:
  - `README.md`, `ARCHITECTURE.md`, `SPEC.md`, `CHANGELOG.md`,
    `CONTRIBUTING.md`
  - Operations: `RUN_LIVE.md`, `CLAUDE_DESKTOP.md`, `POSTGRES.md`,
    `LEMONSQUEEZY.md`, `CI.md`
  - Marketing: `BETA.md` (with crypto-native acquisition channels),
    `DEMO.md` (60s Loom script), `MARKETPLACE.md`
  - Per-marketplace listings: `listings/SMITHERY.md`, `PULSEMCP.md`,
    `GLAMA.md`, `MCPMARKET.md`, `AWESOME_MCP.md`
  - Index: `INDEX.md`
- **134 tests passing, 1 skipped** (Postgres tests skipped without
  `DATABASE_URL_TEST`).

### Pricing model decisions
- Free: 500 calls/mo, 7d retention
- Starter: $19/mo, 1 000 calls, 30d
- Indie: $79/mo, 10 000 calls, 90d
- Pro: $299/mo, 100 000 calls, 1y
- Enterprise: $999+/mo, unlimited (DART-cap-bound), 3y + SLA
- Lifetime: $149 one-time (first 100), INDIE limits forever
- Annual: −20% (subscription tiers only)

### Persona / positioning
- Primary ICP **changed mid-build** from "fund analyst (Sarah)" to
  "crypto-native rotator (Jay)" after observing the rotation pattern.
  Reflected in `docs/SPEC.md`, `docs/BETA.md`, the landing page copy, and
  the prioritization of `monitor_activist_investors` + alerts module.
- Tagline: *"DART is the blockchain explorer for Korean equities."*

### Capacity
- Single DART key supports **~9 500 MAU at 70% cache hit** (current code).
  Scales to ~30 000 MAU at 95% cache; second key required beyond.
- 12-month forecast (756 MAU) consumes 2.9% of daily soft quota
  (~930 DART calls/day) — 34× headroom.

### Bug fixes during build
- DART filing type defaulting to "Other" — DART list.json doesn't return
  `pblntf_ty`. Fixed via title-prefix heuristic.
- Translator provider/model env-var leak — `provider="anthropic"` was
  picking up `KOREANPULSE_TRANSLATE_MODEL=gpt-5-mini` from env. Fixed by
  only applying the env override when the active provider matches the
  default provider.
- `quota_blocks_when_full` test brittle on KST date rollover — fixed by
  using runtime KST date instead of hardcoded `"2026-05-04"`.
- Webhook FastAPI 422 — `from __future__ import annotations` defeated
  FastAPI's runtime introspection of the `Request` parameter. Removed in
  `webhook_app.py` only; module-level FastAPI imports.
- **`ls_subscription_id` / `ls_order_id` empty in license metadata** —
  the Lemon Squeezy webhook was reading the entity ID from
  `attributes.id`, but Lemon Squeezy puts the canonical subscription /
  order ID at `data.id`. Fixed by extracting it once in `handle_event`
  and threading it through to the per-event handlers as `entity_id`.
- **`datetime.utcnow()` deprecation** — one residual call in `dart.py`
  fallback path replaced with `datetime.now(timezone.utc).replace(tzinfo=None)`
  to keep the existing naive-datetime contract on `Filing.filed_at`.

### Cold email round-2 + diaspora channel research (deferred)
- **`_workspace/cold_email_targets_round2_2026-05-05.md`** — 9 net-new
  firms after dedup. Top R2 picks: **JOHCM**, **Hosking Partners**
  (capital-cycle thesis on memory semis explicitly), **Polar Capital
  EM/Asian Stars**, **Polymer Capital**, **Mobius Capital Partners**,
  **Pendal GEM Opps** (flagged do-not-dup with JOHCM — same PM team).
  Substack publishers (Chip Briefing / East Asia Stock Insights /
  Emerging Market Skeptic) reclassified to multiplier_outreach pattern
  (DM/Substack reply, not cold email).
- Negative findings preserved: Korea Fund (now JPMAM-subadvised, out of
  ICP); WisdomTree/First Trust/VanEck Korea ETFs all liquidated or
  non-existent; Asia Frontier Capital excludes Korea; SemiAnalysis is
  a seller not a buyer; "Petra Capital NY" does not exist (Petra is
  Seoul-only). These spare the founder wasted research time.
- **Final combined send-first top 5**: Indus → Hosking → Dalton →
  JOHCM → GAM Alts. Total pool R1(8) + R2(~6 net) = **14 firms**, well
  under 30-cap. Deliberately leaves headroom rather than padding with
  weak fits.
- Korean diaspora channel research (`aa1ee423`) — deferred. Background
  agent hit the day's API usage cap before producing output. Retry after
  the 12:10 KST reset; structure of the prompt is preserved at
  `/tmp/claude-1000/.../tasks/aa1ee423a0cf01683.output` if needed.

### Multiplier outreach + PyPI release pre-flight + surface consistency
Three parallel tracks — two background-agent assisted, one direct:

- **`_workspace/multiplier_outreach_2026-05-05.md`** — Outreach packages
  for Sanghyun Park (Clepsydra Capital, Smartkarma) and Douglas Kim
  (Douglas Research Insights, Substack). Both are Korean equity research
  publishers with English-speaking subscribers — pitched as `multiplier`
  not `buyer`. Asks them to mention koreanpulse to their readership if
  it holds up. Honest pre-alpha disclosure, no marketing language. Park
  message ~165 words (Smartkarma DM), Kim message ~265 words (Substack
  contact form). Both reference `[verify recent piece]` placeholder so
  the founder personalises with an actual published title before sending.
  Includes top-of-file tactical notes (channel, tone, no-translation
  pitch) and bottom triage rules (success/failure/don't-do, no follow-up).

- **`_workspace/pypi_release_checklist_2026-05-05.md`** — Pre-flight memo
  for `git tag v0.1.0`. Identifies one hard blocker: `agentprod` is
  declared as a `[tool.uv.sources]` editable path, which PyPI publish
  ignores — `pip install koreanpulse` users would silently miss the
  dependency. Four options laid out (publish agentprod separately,
  vendor inline, remove dependency, keep GitHub-install only).
  Recommendation: publish agentprod separately. Also includes version-
  bump procedure, trusted-publishing prerequisites, README badge plan,
  and a release-after-marketplace-registration sequencing argument.

- **Surface-consistency pass** — `pyproject.toml` description + keywords
  broadened to match the landing/README anchor. `smithery.yaml`
  display name and description rewritten ("English-first Korean Equity
  Intelligence"). `docs/DEMO.md` final-frame copy updated, `/today`
  surfaced. `docs/ARCHITECTURE.md` tool count `6 → 7`. `docs/BETA.md`
  historical Show HN block marked **superseded** with a pointer to
  `docs/HN_LAUNCH.md` so the founder doesn't accidentally post the W3
  draft.

- User-action runbook step 7 (PyPI release) updated to call out the
  agentprod blocker explicitly.

### Parallel work — Show HN draft, cold-email targets, foreign-volume source decision
Three background tracks completed alongside the main code track:

- **`docs/HN_LAUNCH.md`** — Show HN launch package: 76-char title leading
  with the MCP-client framing, ~395-word body opening on the 2026-04-05
  retail-access inflection (Hana×Futu, Samsung×IBKR, May 4 record),
  honest counterpoint included (-11.8T₩ full-year 2025, IBKR is pilot),
  pivots to multi-source English-IR-gap citation. 95-word self-comment.
  5 prepared Q&A (ChatGPT translation, KED Global compare, latency,
  AGPL+license, foreign-holders curation). Tue/Wed 8:30-9:30am ET timing
  with 5 hard preconditions before posting.
- **`_workspace/cold_email_targets_2026-05-05.md`** — 12 boutique funds
  identified, **8 high-confidence** for the 30-cap cold-email channel
  (Dalton / Oasis / Indus / GAM Alts / Pleiad / Matthews [Elli Lee] /
  Maple-Brown Abbott / FCP). Each row: Korea-coverage evidence URL,
  contact target, email pattern guess (always flagged as guess), notes.
  4 edge-case firms with rationale for deferral. The remaining 22 cold-
  email slots intentionally left empty rather than padded.
- **`_workspace/foreign_volume_source_decision_2026-05-05.md`** — 6-source
  matrix on per-ticker foreign trade volume. Verdict: no source is
  simultaneously ToS-clean + Worker-compatible + has the data. KRX OPEN
  API (effective 2025-12-26) explicitly forbids commercial use and
  third-party redistribution; data.krx.co.kr OTP CSV scrape forbids
  redistribution; data.go.kr KOGL Type 1 has clean license but no
  investor-trend dataset. **KIS Open API (`foreign-institution-total`,
  `inquire-investor`) is the only realistic technical fit** — license
  is silent (gray) but the user already operates KIS in stock-advisor
  and us-advisor. Recommendation: ship via KIS + send written compliance
  question to KIS support, document response. Hard ToS quotes (KO + EN)
  preserved in the memo for the founder's audit trail.

User-action runbook updated with three new entries: KIS compliance
question (step 1b), cold email send list (step 7b), Show HN posting
(step 7c).

### Enrichment helper extracted + tested
- `fill_corp_name_en` moved out of `koreanpulse.server` into a new
  `koreanpulse._enrich` module. The server module imports and calls it.
  Why: `server.py` imports `fastmcp` at module load, so anything inside
  `server.py` is untestable in environments where FastMCP isn't pinned.
  The helper has no FastMCP dependency, so isolating it removes the
  test-time import barrier.
- All three MCP tools (`track_korean_filings`, `monitor_activist_investors`,
  `monitor_foreign_holders`) now pass their already-constructed
  `Translator` instance into the helper explicitly. Cleaner DI and one
  fewer redundant `_get_translator()` call per request.
- 8 new tests in `tests/test_server.py` (named `test_server.py` rather
  than `test_enrich.py` to keep the suite browsable):
  - basic fill from translator
  - skip already-filled rows
  - intra-batch dedup by corp_code (3 rows for same corp → 1 LLM call)
  - distinct corps → distinct calls
  - empty corp_name skipped (no LLM call, no error)
  - translator failure logged + does NOT block (response shape stable)
  - works on `ForeignHolderFiling` (subclass of `Filing`)
  - real `Translator` + `FileCache` integration: second call same corp =
    no extra `_call_llm` (cache hits).
- Total tests: 179 passed (171 → +8). Regression 0.

### English company-name auto-fill (`corp_name_en`)
- New `Translator.translate_corp_name(name_ko)` with a dedicated system
  prompt tuned for short Korean company names (no parenthetical Korean
  appendix, official English form for widely-known companies, Romanise
  otherwise). Cached under a separate namespace (`corp_name:`) so a
  Korean string identical to a filing-title fragment doesn't collide.
- New `_fill_corp_name_en` helper in `server.py`. Each MCP tool that
  serves filings (`track_korean_filings`, `monitor_activist_investors`,
  `monitor_foreign_holders`) now populates `Filing.corp_name_en` when
  `translate=True`. Intra-batch dedup by `corp_code` plus the
  `Translator` cross-batch cache keep cost negligible (≈5 tokens × 1
  LLM call per unique Korean company name, then permanent cache hit).
- Daily Worker mirrored: `daily-worker/src/translate.ts` adds
  `translateCorpName()` + KV namespace `translate:c:`. The cron's
  enrichment functions (`enrichActivists`, `enrichForeign`, `enrichTop`)
  populate `corp_name_en`. `/today` HTML now leads with the English
  name; the Korean name appears as a subtle secondary label only when
  it differs. Discord embed fields prefer English where available.
- `landing/public/llms.txt` JSON schema description updated to declare
  `corp_name_en` as a populated optional field.
- Result: a foreign-retail visitor landing on `/today` immediately
  reads "Samsung Electronics", "SK Hynix", "Celltrion" instead of
  having to recognise the Korean characters first. Direct fix for the
  English-IR gap thesis on the visible surface.
- 3 new tests under `TestCorpNameTranslation` — empty input, cache hit,
  separate namespace from filing-title cache. Total 171 passed.

### MCP tool — `monitor_foreign_holders` + activists module overhaul
- New MCP tool `monitor_foreign_holders` exposing the same foreign-passive-
  holder allowlist that the daily-worker has been using since Day 2 (20
  names: BlackRock, Vanguard, State Street, Fidelity, Capital Group,
  T. Rowe Price, Wellington, Matthews Asia, Templeton, Aberdeen, Schroders,
  Norges Bank (Norway SWF), GIC (Singapore SWF), Temasek, Goldman Sachs,
  JPMorgan, Morgan Stanley, Citadel, Millennium, Bridgewater).
  - Distinct from `monitor_activist_investors` because passive holders
    signal *allocation* rather than *governance pressure*.
  - Returns `ForeignHolderFiling` rows with `holder_label` (canonical
    English) and `holder_origin` (`us` / `uk` / `eu` / `other` / `kr`).
  - Optional `origin` arg filters by country.
  - Uses the same DART list endpoint as `monitor_activist_investors` —
    no extra quota cost.
- `koreanpulse.activists` module rewritten to a unified `InvestorRecord`
  schema with `klass: InvestorClass` (`activist` | `foreign`) and
  `origin`. `KOREAN_ACTIVISTS` (10 entries, klass=activist) and
  `FOREIGN_HOLDERS` (20 entries, klass=foreign) are tuples of the same
  type; `ALL_INVESTORS = KOREAN_ACTIVISTS + FOREIGN_HOLDERS`.
- New matchers: `match_investor` (returns full `InvestorMatch` with
  klass+origin), `match_foreign_holder` (foreign only). Existing
  `match_activist` retained for backwards compat — now delegates to
  `match_investor` and returns activist-class matches only.
- `koreanpulse.models.ForeignHolderFiling` added (Pydantic model;
  `holder_label`, `holder_origin` fields).
- `koreanpulse_about` tool surface extended: `tools_available` from 6 → 7.
- `landing/public/.well-known/mcp.json` `tools` array adds
  `monitor_foreign_holders` row. `landing/app/page.tsx` "What you get"
  grid surfaces the new tool prominently as the first row (tied to the
  2026 inflection narrative).
- 14 new tests (`test_activists.py::TestMatchForeignHolder`,
  `TestMatchInvestor`, registries). Total 168 passed (was 154).

### Daily Worker Day 3 — content depth (takeaway + 2026 inflection box)
- **Today's takeaway** — LLM-generated 1–3 short English bullets at the top
  of `/today`, summarising the single most material moves of the day. Built
  from a compact JSON digest of foreign / activist / major filings so the
  LLM doesn't chew through every field. Cached per (date + digest hash) so
  manual `/admin/rebuild` doesn't burn extra OpenAI calls when data is
  unchanged. Cost: 1 extra OpenAI call/day (≈$0.001).
- **"2026 inflection" callout box** on `/today` — static green-bordered
  panel just above the Foreign capital activity section, surfacing the
  IRC abolishment + Hana×Futu + Samsung×IBKR + 2026-05-04 record net-buy
  context. Anchors retail visitors on "why this dashboard exists right
  now" the moment they land.
- **JSON schema bumped to v2** — additive `takeaway: string[]` field at
  the top level. `llms.txt` schema description updated so AI clients
  know to consume it.
- **Discord embed description leads with takeaway** — readers who never
  click through still get the headline. Filing counts shift to a
  subordinate italicised line.
- **Render layout reordered** — Today's takeaway → 2026 inflection →
  Foreign capital activity → Activist filings → Major filings. The
  takeaway is the daily retention hook; the inflection is the once-only
  "why now" hook.
- Free-tier budget impact: +1 OpenAI call/day (gpt-5-mini), +2 KV reads/
  writes (cache + snapshot). Still well under 1% of any free-tier limit.

### Foreign retail KRX inflow audit + timing news hook
- Second audit (`_workspace/foreign_retail_inflow_2026-05-05.md`) on the
  user's claim that foreign retail (외국개미) inflow into KRX has surged.
  Verdict: **directionally strongly supported** by hard data, even though
  English self-identification (the first audit) was thin. The two
  layers are not contradictory — they answer different questions.
- Hard data captured:
  - 2025-12-14: IRC (Investor Registration Certificate) abolished →
    foreign account openings +3–4× rate vs 2023 baseline (FSC).
  - 2026-04-late: Hana Securities × Futu Securities (3.3M HK fintech
    retail) launched direct Korean stock trading.
  - 2026-05-04 (yesterday): Samsung Securities × Interactive Brokers
    (4.6M global retail) pilot launched. Same day: foreigners
    net-bought a record 3.9T₩ (~$2.7B) on KOSPI+NXT.
  - **~7.9M foreign retail accounts now have a wired path into KRX, up
    from ~0 two years ago.**
- Counter-evidence kept honest: 2025 net foreign sales were −11.8T₩
  (mark-to-market on the rally, not new dollars). IRC openings still
  85% institutional. IBKR pilot not yet production. Foreign retail is
  a 12-month narrative bet, not a 3-month revenue base.
- **Timing news hook propagated to surfaces**:
  - `landing/app/page.tsx` adds a "2026 inflection" callout box above
    the existing "Why" section, listing the IRC, Futu, IBKR, and
    May-4-record events with sources.
  - `README.md` "Why this exists" prepends the inflection bullet so
    GitHub visitors see the timing first.
  - `landing/public/llms.txt` adds a paragraph about the inflection so
    AI search summaries (ChatGPT / Claude / Perplexity) carry the
    timing context.
- Strategic split (PMF auditor recommendation):
  - Short-term revenue (≤3 months): institutional first
    (PulseMCP / cold email / industry conferences).
  - Long-term funnel (12-18 months): foreign retail Discord/web
    (current track maintained — Daily Worker `/today`, role
    instrumentation, marketplace listings).
  - Content angle: the IBKR/Futu launch dates ARE the news hook for
    inbound traffic. Treat the 2026-04-05 inflection as the launch
    narrative.

### Marketplace listing copy — broadened to match landing/README anchor
- All 5 listing files (`docs/listings/{SMITHERY,PULSEMCP,GLAMA,MCPMARKET,
  AWESOME_MCP}.md`) rewritten to mirror the landing-page anchor
  (English-IR gap multi-source verified) and the new tool surface (6
  tools including `monitor_activist_investors` with foreign-holder
  classification).
- Each listing now surfaces:
  - The free public daily snapshot at `koreanpulse.dev/today` as a
    no-friction demo entry point (drives stars before formal review).
  - The 20-name foreign-holder allowlist (BlackRock / Vanguard / Norges
    / GIC / Temasek / Goldman / JPM / Morgan Stanley / Citadel /
    Millennium / Bridgewater + 9 more).
  - Hosted-mode env config (`KOREANPULSE_CACHE_MODE=hosted` +
    `KOREANPULSE_LICENSE_KEY`) alongside the BYOK default.
  - Multi-audience framing (foreign analysts, crypto rotators, Korean
    diaspora, EM journalists, MCP developers) instead of the old
    "foreign fund analysts" exclusive frame.
- Listing copy is now consistent across surfaces — landing, README,
  mcp.json, llms.txt, and the 5 marketplace files all carry the same
  anchor message and tool list.

### Positioning broadening + audience composition instrumentation
- **Carbon-copy applied** of `_workspace/user_research_2026-05-05.md`
  finding (English retail self-identification = 0 quotes; multi-source
  English-IR-gap signal = strong) to all customer-facing surfaces:
  - `landing/app/page.tsx` Hero rewritten to "English-first Korean equity
    intelligence — for analysts, rotators, and AI agents." Top nav now
    surfaces `/today`, `/pricing`, `github`. New "Free daily snapshot"
    section linking `/today`. "Why people are paying attention to KRX"
    leads with the institutional English-IR gap (KRX, ASIFMA, Wellington)
    rather than crypto-only framing. Crypto rotation kept as one of five
    bullets, not the only frame.
  - `README.md` headline + pitch broadened. "Who pays" table extended
    with crypto-native rotator + Korean diaspora rows (alongside the
    original journalist / boutique fund / multi-strat audiences).
  - `landing/public/.well-known/mcp.json` description rewritten — surfaces
    foreign-holder allowlist (BlackRock / Vanguard / Norges / GIC /
    Temasek) + activist coverage + free daily web snapshot.
  - `landing/public/llms.txt` first paragraph re-anchored on the
    multi-source English-IR-gap thesis.
- **Audience composition signal at signup**:
  - Landing `/api/notify` accepts optional `role` field with allowlist
    `analyst | rotator | diaspora | journalist | developer | other`;
    unknown values normalise to `unknown`. Logged with each signup.
  - Email-capture form on landing now exposes a dropdown using the same
    options ("I'm a…"). Optional — not required, to avoid drop-off.
  - **Lemon Squeezy webhook captures the same `role` field at checkout**
    via `_extract_self_description()` — tries 3 paths in order:
    `meta.custom_data.role`, `attributes.first_order_item.product_options.custom.role`,
    `attributes.custom_fields_responses.role`. Allowlist-validated;
    unknown values normalise to `"other"`. Stored at
    `License.metadata.self_description`. Preserved on subscription updates
    so a later upgrade without a payload role doesn't blank a prior value.
  - 5 new tests cover the path matrix + preservation + normalisation.
  - Operator setup: `_workspace/user_actions.md` step 2 now includes the
    LS custom field configuration (field name `role`, dropdown options,
    optional). System works without the field — only audience signal
    is foregone.
- **Day-7 measurement query added** to runbook — Postgres
  `metadata->>'self_description'` GROUP BY for live audience composition
  during beta. Validates / invalidates the original "Jay rotator" thesis
  with paying customer data.

### Daily Worker Day 2 — Foreign capital activity + AI-friendly schema
- **Foreign-holder allowlist** (`activists.ts` extended) — 20 global asset
  managers / sovereign wealth funds known to file Korean 5%-rule
  disclosures (BlackRock, Vanguard, State Street, Fidelity, Capital Group,
  T. Rowe Price, Wellington, Matthews Asia, Templeton, Aberdeen, Schroders,
  Norges Bank / Norway SWF, GIC, Temasek, Goldman Sachs, JPMorgan,
  Morgan Stanley, Citadel, Millennium, Bridgewater). New `InvestorClass`
  ("activist" | "foreign") + `origin` field for flag display.
- **Single DART call services both streams** — `fetchClassifiedFilings`
  pulls type-D filings once and routes filers to activist vs foreign
  buckets. No extra quota cost over Day 1.
- **`/today` page**: new "Foreign capital activity" section above
  activists, color-coded emerald, country-flag prefix. Section copy
  explains it as a leading indicator of foreign money entering or exiting
  a Korean ticker.
- **JSON schema versioned** — `/today.json` now includes `schema_version: 1`,
  `market: "KRX"`, `data_sources`, `legal_notice` fields. AI clients can
  pin against the version for stable parsing.
- **Discord push** updated to surface foreign-holder filings first
  (4 each: foreign + activist + major), 💰/🚨/📄 icons.
- **`llms.txt`** prepended a "Daily snapshot (machine-readable)" section
  documenting `/today`, `/today.json` schema, and `/today/YYYY-MM-DD`
  history routes — so LLM crawlers index the live data surface, not just
  the README.
- **Why "foreign 5%-rule" instead of daily KRX trade tape**: `data.krx.co.kr`
  daily-trade-by-investor data only ships through an OTP-token web pattern
  (ToS gray); foreign 5%-rule filings are 100% public DART data with no
  ToS friction. Day 1+2 sticks to the legal-safe path. Daily-trade tape
  is queued for v1 once a clean source decision is made.

### Audience evidence audit (`_workspace/user_research_2026-05-05.md`)
- Independent research pass on the "crypto → KRX rotation" thesis.
- Verdict: macro evidence is strong (Upbit -80% YoY, KOSPI +76%, MSCI DM
  consideration, Korean tax abolition). Direct retail self-identification
  in English public forums is **0 quotes** after extensive Reddit / HN /
  Twitter search.
- Real, multi-source-verified pain point is the **English-language IR /
  disclosure gap** (KRX, ASIFMA, Wellington, Aberdeen, Matthews Asia all
  on record). Foreign-holder filings section is anchored on this.
- Counter-signals captured: Korea-discount narrative on HN, March 2026
  KOSPI -18% crash, Korean retail rotating *out* to US stocks (CNBC).
- Implication: keep "DART is KOSPI's blockchain explorer" framing as
  secondary; lead with "English-first KRX intelligence" as the
  multi-source-verified anchor.

### Daily Worker — `koreanpulse.dev/today` (form pivot)
- New top-level `daily-worker/` package — second Cloudflare Worker that
  builds a free-tier daily Korean equity dashboard for crypto-native
  rotators showing up daily on the web. The MCP server stays as the
  agent / API surface; this Worker is the human-readable funnel front
  door.
- Cron trigger `30 7 * * 1-5` (KST 16:30, post-KOSPI-close) does:
  pull DART type-D filings (7d) + type-A/B (1d) → activist match → OpenAI
  title translation + ≤80-word summaries → write HTML + JSON to KV →
  Discord webhook push (if configured).
- Routes: `GET /today` (HTML, 5-min edge cache), `/today.json` (machine),
  `/today/:date` (30-day history), `/admin/rebuild` (manual trigger
  guarded by DART key as shared admin secret).
- Resource budget: ~3 DART calls/day, ~5 fresh OpenAI calls/day
  (gpt-5-mini, ≈ $0.15/month), 5 KV writes/day, 1 cron tick. All within
  Cloudflare's free tier indefinitely until ~5k visitors/day.
- Brand-aligned plain HTML render (Tailwind via CDN, < 30 KB). No
  client-side JS. Edge-cached so first paint is instant.
- TS port of `koreanpulse.activists` (`KOREAN_ACTIVISTS` allowlist) —
  10 entries, kept in sync with the Python module. Same matcher
  semantics (case-insensitive substring, KO + EN aliases).
- Discord push: brand-amber embed, ≤5 activist + ≤5 major filings as
  fields, fire-and-forget (failure logs but never blocks the build).

### Documentation refresh
- `docs/CLAUDE_DESKTOP.md` rewritten to cover BYOK *and* hosted modes:
  decision matrix at the top, env-var split between modes, both config
  templates, and a failure-mode table mapping common errors to fixes.
- `README.md` "Architecture" section corrected to reflect the
  three-component split (MCP server on user machine + Cloudflare Worker +
  webhook on Lightsail). New "BYOK vs Hosted" section above pricing
  surfaces the hosted cache value to readers landing on GitHub.
- `_workspace/user_actions.md` (new) — operator runbook covering
  domain / Lemon Squeezy / Cloudflare / Lightsail / Vercel / PyPI /
  marketplace registrations + decision-matrix measurement triggers.
  Lists what user must do, what to relay back to claude, and what is
  hard-prohibited (no own posts / no paid ads / no cron daemons / no
  new tools at 0 paid).

### Discovery surface (`/.well-known/mcp.json` + `/llms.txt`)
- Added `landing/public/.well-known/mcp.json` — self-describing MCP server
  manifest (6 tools, 5 env vars, 6 pricing tiers, data-source license terms,
  legal posture). Once the landing is deployed at `koreanpulse.dev`,
  marketplace crawlers (Smithery, PulseMCP, Glama) and agent discovery
  tools can index the server without hand-curated submissions.
- Added `landing/public/llms.txt` — site description in the
  [llms.txt](https://llmstxt.org) format. Provides Claude / ChatGPT /
  Perplexity with a curated map of README, SPEC, ARCHITECTURE, BETA,
  pricing, and tool implementations so search-grounded AI summaries
  describe the product accurately rather than hallucinating from
  page-scraping. `## Optional` section marks lower-priority docs.
- Both files are static — Next.js `public/` serves them at the apex
  domain root with zero routing code. No tests required (data files,
  not code paths).

### Translator BYOK / Hosted dispatch
- `Translator` now supports two cache modes via `KOREANPULSE_CACHE_MODE`:
  - `local` (default) — direct OpenAI/Anthropic call + local `FileCache`,
    suitable for free / BYOK users with their own provider key.
  - `hosted` — POST to `koreanpulse-cache` Worker `/v1/translate` with the
    user's `KOREANPULSE_LICENSE_KEY`. The Worker holds our OpenAI key and
    fronts a global KV cache, so paid users get the cross-tenant cache hit
    rate that drives margin.
- Hosted-mode failures **never fall back** to local. A 4xx/5xx from the
  Worker raises `TranslationError` immediately so the paid value remains
  visible (no silent BYOK substitution under outage). The error message
  guides the user to switch to `KOREANPULSE_CACHE_MODE=local` if they
  want to keep working offline of the Worker.
- License key never logged in full — only the first 8 characters appear
  in warning logs (`license=kp_abcdef…`).
- New env vars (all optional, surfaced in `.env.example`):
  `KOREANPULSE_CACHE_MODE`, `KOREANPULSE_CACHE_URL`,
  `KOREANPULSE_LICENSE_KEY`.
- New `Translator(http_client=...)` parameter for test injection (matches
  the existing pattern used by `dart.list_filings`).
- 8 new tests in `test_translate.py::TestHostedMode` covering: default
  mode, env selection, unknown mode, missing license key, translate POST
  shape, summarize attribution propagation, immediate-fail on 402, and
  local-cache-bypass invariant.

### Cache Worker (Cloudflare Workers + KV)
- New top-level `cache-worker/` package — TypeScript Cloudflare Worker that
  hosts the global translation/summary cache and gates it behind a license
  check. Free tier covers 100K req/day on Workers + 100K reads/day on KV,
  so paid traffic generates no per-user compute cost on our side.
- `POST /v1/translate` accepts `{ kind, text, attribution?, license_key }`
  and returns `{ output, cached, provider, model }`. KV cache key folds
  provider+model into the digest so model swaps don't poison cache.
  Translations cached forever; summaries 30-day TTL.
- License validation hop to `koreanpulse-webhook /v1/validate` is HMAC-SHA256
  signed (shared secret) and the *successful* result is cached in the per-colo
  Cache API for 60s, so each license generates ≈ 1 validate/min/colo of
  Postgres pressure no matter how many translation calls fly through.
  Failures are not cached — a cancellation is picked up within seconds.
- Worker → webhook secret: `KOREANPULSE_CACHE_SHARED_SECRET`. Set the same
  value on both sides (env var on the webhook, `wrangler secret put` on the
  Worker). Webhook returns 401 on signature mismatch, 500 if unconfigured.

### Hardening
- **Postgres production guard** — `koreanpulse` and `koreanpulse-webhook`
  now refuse to start when `KOREANPULSE_REQUIRE_LICENSE=1` but
  `DATABASE_URL` is not set. The webhook process and the MCP server are
  separate Python processes; without a shared Postgres license store, a
  key issued by one would never be visible to the other. The guard is
  lazy/cooperative — `aget_default_store()` autoconnects Postgres when
  `DATABASE_URL` is set, otherwise falls back to `InMemoryLicenseStore`
  in dev mode (`KOREANPULSE_REQUIRE_LICENSE` unset).
- **`LicenseStore` Protocol formalized** — `find_by_email(email)` and
  `next_lifetime_seq()` are now part of the Protocol. Both
  `InMemoryLicenseStore` and `PostgresLicenseStore` implement them
  natively; the previous private-attribute fallbacks
  (`store._data`) in `lemonsqueezy.py` are gone.

### Security notes
- `OPENAI_API_KEY` accidentally committed to `.env.example` during dev →
  user rotated key after the leak window. `.env.example` reverted to
  placeholder.
- `.env` is gitignored. `.env.example` is the only env-related file
  intended for git.

[Unreleased]: https://github.com/whdrnr2583-cmd/koreanpulse/commits/main
