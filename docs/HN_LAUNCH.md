# Show HN launch package — koreanpulse

Single-shot submission kit. Copy the title, copy the body, post the self-comment within 60 seconds of submission. Do not edit-loop the post after it goes live.

---

## 1. HN title (76 chars)

```
Show HN: Koreanpulse – English data layer for Korean equities, in your MCP client
```

Alt if the above feels long:

```
Show HN: Koreanpulse – Korean equity disclosures in English, via MCP
```

Pick the first. The "in your MCP client" is the differentiator that separates it from yet-another-news-API.

---

## 2. HN post body

The hook leads with the workflow tilt — watchlist → English alert — so HN
readers don't dismiss this as "another MCP server."

```text
Last week was a real inflection for foreign access to Korean equities, and
it's the reason I'm posting this now instead of in three months.

What koreanpulse will do, in one sentence: you give it your KRX tickers
and it pings you in English the moment a 5%-rule filing or material DART
event hits one of them. Watchlist in, English alert out. Honest status
note up front: queries + the hosted English translation cache are live
today; the watchlist polling loop and alert dispatch ship Q3 2026 — this
is a waitlist post, not a "buy today" post. The MCP plumbing is an
implementation detail.

- Late April: Hana Securities x Futu (3.3M HK retail accounts) went live on
  Korean stocks.
- May 4: Samsung Securities x Interactive Brokers (4.6M global retail) opened
  a pilot. Same day, foreigners net-bought a record 3.9T KRW (~$2.7B) on
  KOSPI+NXT — the largest single-day print on record.
- December 2025: the IRC (foreign investor registration certificate) was
  abolished. Foreign account openings are running 3-4x the 2023 baseline.

Honest counterpoint: full-year 2025 net foreign flow was still -11.8T KRW,
and the IBKR side is a pilot, not a full rollout. So this is "early to a
real trend," not "the trend has arrived." But the wiring is now in place
for ~7.9M foreign retail accounts that previously had no path in.

The English-language data side has not caught up. KRX, ASIFMA, Wellington,
Aberdeen, and Matthews Asia are all on record that Korean disclosure flow
into English is structurally inadequate. I run a Korean automated trading
system and hit this every day — Bloomberg is $24K/yr and still misses the
front page of 전자신문.

Koreanpulse is being built as the English-language data layer for that
audience.

Two surfaces, one stack:
1. Free public snapshot at koreanpulse.dev/today (no login, no key, JSON
   at /today.json, 3-day archive). Live now. Treat it as a preview of the
   daily digest paying customers will get pushed to their channel.
2. Cloud waitlist — early-supporter rate locked in. Watchlist polling +
   alert dispatch ship Q3 2026; queries + hosted translation are live
   today (you still install the local MCP, but no OpenAI key needed —
   the Cloudflare Worker holds ours and validates your license):
   - Cloud Solo $29/mo — 5 watchlists, ~2,000 queries/mo, 30-day archive,
     1 Discord/Telegram channel, daily English digest.
   - Cloud Analyst $79/mo — 25 watchlists, ~15,000 queries/mo, 1-year
     archive, multi-channel alerts, CSV/JSON export, priority cache.
   - Cloud Desk $249/mo — 3 seats, shared watchlists, ~100,000
     queries/mo, Slack/webhook alerts, team archive.
   No auto-charge until the workflow ships. (Watchlist-count, channel-
   count, retention, and seat enforcement land Q3 2026; today the only
   enforced delta between tiers is the monthly query cap.)
3. OSS self-host for hackers — AGPL, bring your own DART + OpenAI keys,
   community support only. Not a pricing tier; a separate lane.

What runs under the hood (7 MCP tools):

- track_korean_filings — DART filings, EN-translated on demand
- monitor_foreign_holders — 20 global passive holders tagged (BlackRock,
  Vanguard, Norges Bank, GIC, Temasek, Capital Group, Matthews, etc.)
- monitor_activist_investors — KCGI, Align, Truston, Anda, Cha, VIP,
  ValueAct, Elliott
- lookup_corp_code / resolve_stock_code — 117K Korean entities, with
  auto-translated English names
- search_korean_industry_news — etnews + 한국경제, 16 industry tags

Build notes: FastMCP on the server, Cloudflare Workers + KV + D1 in
front, zero servers I run myself. Whole thing costs <$15/mo at beta
scale. Source is AGPL.

Looking for: people who actually cover Korea from outside Korea — analysts,
PMs, journalists, activist-fund staff. Two questions I'd love feedback on:
(1) which DART form types matter most to you that I haven't covered yet,
and (2) is the Solo/Analyst/Desk ladder the right shape, or am I missing
a tier?

Repo: github.com/whdrnr2583-cmd/koreanpulse
Daily: koreanpulse.dev/today
```

Word count: ~470. Slightly over 400 but the workflow paragraph + tier
breakdown earns the extra length.

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
- Hosted HTTP-transport endpoint is live today via Smithery
  (smithery.ai/servers/whdrnr2583/koreanpulse — `koreanpulse--whdrnr2583.run.tools`).
  Clients that speak Streamable HTTP can connect with no `pip install` at
  all. Local stdio remains the canonical path for self-hosters and
  max-privacy users; a first-party Cloudflare-hosted HTTP transport is
  still on the roadmap for users who want the endpoint outside Smithery.
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

1. `koreanpulse.dev/today` has at least **3 consecutive successful cron builds** showing real DART filings, not the placeholder. First-time visitors will check this immediately.
2. `/today.json` returns a non-empty `filings` array.
3. At least one of Smithery / PulseMCP / Glama listing is live and links resolve.
4. `pip install koreanpulse` works on a fresh venv on macOS and Linux.
5. The repo's README top-of-fold matches the HN body claims (no stale "coming soon" sections).

If any of those are not green, **delay 24h**. A Show HN that lands on a 404 or an empty demo page burns the post — you only get one for this project.

**Do not:**
- Post on Friday (weekend traffic is lower-quality).
- Post in the first week of a US holiday.
- Edit the post text after submission. If you mistype, post a self-comment correction instead.
- Reply defensively to negative comments. The HN audience reads tone before content.

**Do:**
- Be in front of the keyboard for the first 90 minutes after posting.
- Answer every top-level comment within an hour for the first 3 hours.
- If a comment surfaces a real bug, fix it live and reply with the commit SHA.
