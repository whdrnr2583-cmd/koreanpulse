# Show HN launch package — koreanpulse

Single-shot submission kit. Copy the title, copy the body, post the self-comment within 60 seconds of submission. Do not edit-loop the post after it goes live.

---

## 1. HN title (80 chars — HN hard limit is 80; the comma'd version is 81 and gets rejected)

```
Show HN: Koreanpulse – English data layer for Korean equities in your MCP client
```

(Earlier draft had a comma after "equities" — that's 81 chars, HN rejects it. Comma removed.)

Alt if needed:

```
Show HN: Koreanpulse – Korean equity disclosures in English, via MCP
```

Pick the first. The "in your MCP client" is the differentiator that separates it from yet-another-news-API.

---

## 2. HN post body (4000-char compressed — HN text field hard limit is 4000)

The original ~5344-char draft was rejected (4000 limit). This compressed version
cuts the full holder/activist name dumps and the per-tier pricing card (→ link to
/pricing) while keeping the workflow hook, the market-inflection proof, and the
honest counterpoints. Paste verbatim into the `text` field; leave `url` blank.

```text
The past month has been a real inflection point for foreign access to Korean equities — that's why I'm posting now rather than in three months.

One sentence: give koreanpulse your KRX tickers and it pings you in English the moment a 5%-rule filing or material DART event hits one. Watchlist in, English alert out. Honest status: on-demand queries + a hosted English translation cache are live today; the watchlist polling loop + alert dispatch ship Q3 2026 — so today's value is the query + English layer, not the alerting cron. The MCP plumbing is an implementation detail.

Why now:
- Late April: Hana Securities x Futu (3.3M HK retail accounts) went live on Korean stocks.
- May 4: Samsung Securities x Interactive Brokers (4.6M global retail) opened a pilot. Same day, foreigners net-bought a record 3.9T KRW (~$2.7B) on KOSPI+NXT — the largest single-day print on record.
- 2023-12-14: the IRC (foreign investor registration certificate) requirement was abolished, removing the decades-old registration step for direct foreign access to KRX.

Honest counterpoint: 2025 net foreign flow was still -11.8T KRW and the IBKR side is a pilot — so "early to a real trend," not "arrived." But the wiring is now in place for ~7.9M foreign retail accounts that had no path in before.

The English-language data side hasn't caught up. KRX, ASIFMA, Wellington, Aberdeen and Matthews Asia are all on record that Korean disclosure flow into English is structurally inadequate. I run a Korean automated trading system and hit this daily — Bloomberg is $24K/yr and still misses the front page of 전자신문. Koreanpulse is the English data layer for that audience.

Three lanes, one stack:
1. Free public snapshot at koreanpulse.dev/today — no login, no key, JSON at /today.json, 3-day archive. Live now; a preview of the daily digest paying users get pushed to their channel.
2. Cloud (waitlist, early-supporter rate locked): Solo $29/mo, Analyst $79/mo, Desk $249/mo — rising query caps, archive length, channels, seats; full breakdown at koreanpulse.dev/pricing. Hosted translation means no OpenAI key needed (a Cloudflare Worker holds ours + validates your license). No auto-charge until the polling/alert workflow ships; today the only enforced tier delta is the monthly query cap + seat count.
3. OSS self-host — AGPL, bring your own DART + OpenAI keys, community support only. A separate lane, not a pricing tier.

Under the hood — 7 MCP tools: track_korean_filings (DART filings, EN-translated on demand); monitor_foreign_holders (20 global passive holders tagged — BlackRock, Vanguard, Norges Bank, GIC, Capital Group, Matthews, etc.); monitor_activist_investors (17 Korean activist funds tagged — KCGI, Align Partners, Must, Dalton, Oasis, Palliser, etc.; plus Elliott/ValueAct when they file in Korea); lookup_corp_code / resolve_stock_code (117K Korean entities, auto-translated English names); search_korean_industry_news (etnews + 한국경제, 16 industry tags). FastMCP server, Cloudflare Workers + KV + D1 in front, zero servers I run, source AGPL.

A few other Korean-equity MCP servers exist (korea-stock-mcp, SongT-50/korean-stock-mcp, etc.) — mostly stdio-only, so a user has to npx-install and edit a JSON config first. Koreanpulse runs the latest Streamable HTTP transport at mcp.koreanpulse.dev/mcp — a ChatGPT or Claude.ai user adds it as a custom connector with one URL paste, no install, no config. Pair that with 30 named-entity classifications that raw DART feeds can't derive, and that's our lane. If you need raw KRX OHLCV or XBRL financials, korea-stock-mcp is excellent for that and we keep it out of scope.

Looking for: people who cover Korea from outside Korea — analysts, PMs, journalists, activist-fund staff. Two questions: (1) which DART form types matter most that I haven't covered, and (2) is the Solo/Analyst/Desk ladder the right shape, or am I missing a tier?

Repo: github.com/whdrnr2583-cmd/koreanpulse
Daily: koreanpulse.dev/today
```

~3850 chars. If HN still complains, delete the "FastMCP server, ..." sentence.

---

## 3. Self-comment (post within 60s of submission)

```text
A few things that didn't fit:

- AGPL + Cloud: source is AGPL, but the license-key server isn't, and the
  curated 20-name foreign-holder allowlist + activist allowlist are data,
  not code. OSS self-host gets you the engine, not the curated lists or
  (once it ships, Q3 2026) the watchlist polling that actually pings you.
  The Cloud tiers fund the curation, the cron, the cache fleet, and the
  alert dispatch.
- What's NOT in v0: no real-time intraday quotes (KRX licenses those and
  I'm not paying yet), no KOSDAQ activist coverage (KOSPI only at launch),
  no Korean-language UI (it's deliberately English-first). Watchlist
  polling + alert dispatch + per-tier limit enforcement (watchlist count,
  channel count, retention, seats) are the Q3 2026 ship target — schema
  and alert primitives are shipped, the cron loop wiring them together
  lands then. Today's enforced tier delta is the monthly query cap and
  seat count only; everything else on the pricing card is a paper limit
  until polling ships.
- First-party hosted Streamable-HTTP endpoint at
  `https://mcp.koreanpulse.dev/mcp`. Add it as a custom connector in
  ChatGPT (Settings → Connectors) or Claude.ai (Settings → Connectors)
  and the 5 free tools answer immediately, no pip install, no JSON
  config. Local stdio install via PyPI (`pip install koreanpulse`) is
  still the canonical path for self-hosters and max-privacy users —
  pick whichever fits.
- Day job: I run a live Korean automated trading system. Koreanpulse fell
  out of the same data pipeline I built for myself.
```

~140 words. Comment-ready.

---

## 4. Likely HN questions + prepared answers

**Q: Why not just paste DART pages into ChatGPT and translate?**
A: That works once. It doesn't work for 200 filings/day across 117K entities, and ChatGPT can't tag a Capital Group 5%+ filing as "passive holder" vs. KCGI as "activist" without the curated allowlist. Translation is the easy part. Classification + dedup + delivery into the tool you already have open is the hard part.

**Q: How does this compare to KED Global / Korea Bizwire?**
A: Those are English-language news outlets — human-edited, headline-driven, half-day to one-day latency. Koreanpulse is structured data, not articles: filings, holders, industry feeds, all addressable by ticker or corp code from inside an MCP client. Different shape. They're complements, not competitors.

**Q: What's the latency from DART filing to /today?**
A: DART pushes a filing list every ~2 minutes during KRX hours. The Worker polls and writes to KV inside that window, so /today.json is typically 2-5 minutes behind the source. The MCP tool calls hit DART live, so for paid users it's effectively real-time minus DART's own publish delay.

**Q: Why a license key model when source is AGPL?**
A: AGPL covers the engine. The hosted Cloud tiers include the curated allowlists, the cache fleet, the daily build, and (once shipped, Q3 2026) the watchlist polling cron + alert dispatcher + a support channel. If you want to self-host, fork it and run it — community support only. If you want the watchlist-to-alert workflow with no cron of your own once it ships, Cloud Solo at $29/mo is the locked-in floor for waitlist sign-ups.

**Q: Is the foreign-holders list maintained or scraped?**
A: Maintained. It's a fixed allowlist of 20 globally-known holders (BlackRock, Vanguard, Norges Bank, GIC, Capital Group, Matthews, etc.) matched against DART 5%+ ownership filings. New names get added when a meaningful filer shows up; I don't auto-add every fund that crosses the threshold because the signal-to-noise breaks down fast.

---

## 5. Submission timing

**Window: Tuesday or Wednesday, 8:30-9:30am ET.**

That's 9:30-10:30pm KST — late enough that you can monitor comments for 2-3 hours before sleeping. Wednesday is marginally better than Tuesday because the front-page churn from Monday's backlog has cleared.

**Hard preconditions before posting:**

0. **The HN account is not brand-new.** HN blocks Show HN from fresh accounts (confirmed 2026-05-12: account `jongguk` created same day → "temporarily restricting Show HNs ... mostly by users who aren't yet familiar with the site"). Heuristic readiness: account age ≥ ~7 days AND karma ≥ ~5, earned from substantive comments (NOT self-promo). The real test is whether the submit form accepts it. `_workspace/check_daily.sh` tracks `jongguk` karma+age daily.
1. `koreanpulse.dev/today` has at least **3 consecutive successful cron builds** showing real DART filings, not the placeholder. First-time visitors will check this immediately.
2. `/today.json` returns a non-empty `filings` array.
3. At least one of Smithery / PulseMCP / Glama listing is live and links resolve.
4. `pip install koreanpulse` works on a fresh venv on macOS and Linux.
5. The repo's README top-of-fold matches the HN body claims (no stale "coming soon" sections).

If any of those are not green, **delay**. A Show HN that lands on a 404 or an empty demo page burns the post — you only get one for this project. (And don't try to sneak past #0 by posting koreanpulse.dev as a non-"Show HN" link — that's the exact spam pattern HN is filtering; it gets flagged.)

**Do not:**
- Post on Friday (weekend traffic is lower-quality).
- Post in the first week of a US holiday.
- Create a second HN account to bypass the Show HN restriction.
- Edit the post text after submission. If you mistype, post a self-comment correction instead.
- Reply defensively to negative comments. The HN audience reads tone before content.

**Do:**
- Be in front of the keyboard for the first 90 minutes after posting.
- Answer every top-level comment within an hour for the first 3 hours.
- If a comment surfaces a real bug, fix it live and reply with the commit SHA.
