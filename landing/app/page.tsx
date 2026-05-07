"use client";

import { useState } from "react";

const PRICING = [
  {
    name: "Cloud Solo",
    price: "$29/mo",
    audience: "Individual traders, solo analysts",
    checkoutUrl:
      "https://buy.polar.sh/polar_cl_ETpLepEvpGkGBXAOJjQhi7gwizO8GkOW3YaHw4IgHAr",
    features: [
      "Unlocks 2 paid MCP tools: monitor_activist_investors + monitor_foreign_holders",
      "Korean activist filer match — KCGI / Align Partners / Truston / Anda / Cha / VIP / Life / Platform / ValueAct / Elliott",
      "Foreign-holder allowlist — BlackRock / Vanguard / Norges / GIC / Temasek / Goldman / JPM + 13 more",
      "Hosted translation cache (no OpenAI key needed)",
      "~2,000 queries/mo (live today)",
      "5 watchlists (Q3 2026)",
      "30-day archive search (Q3 2026)",
      "1 Discord or Telegram alert channel (Q3 2026)",
      "Daily English digest (live today)",
    ],
  },
  {
    name: "Cloud Analyst",
    price: "$79/mo",
    audience: "Boutique fund analysts, paid-research-budget retail",
    highlighted: true,
    checkoutUrl:
      "https://buy.polar.sh/polar_cl_PmbLKURPhVZ1wuh6vqEKOXx4UNcii3bDqtFg62komUR",
    features: [
      "Everything in Solo (2 paid MCP tools + classification)",
      "~15,000 queries/mo (live today)",
      "25 watchlists (Q3 2026)",
      "1-year archive search (Q3 2026)",
      "Multi-channel alerts (Discord / Telegram / Email) (Q3 2026)",
      "Saved searches (Q3 2026)",
      "CSV / JSON export (Q3 2026)",
      "Priority cache + priority refresh",
    ],
  },
  {
    name: "Cloud Desk",
    price: "$249/mo",
    audience: "Small research teams, boutique long/short desks",
    checkoutUrl:
      "https://buy.polar.sh/polar_cl_l6B5yiFOQqWIkyFpHtkTl93YzaEGWnzHtxDQ4393h7j",
    features: [
      "Everything in Analyst (2 paid MCP tools + classification)",
      "~100,000 queries/mo (live today)",
      "3 seats, shared watchlists (Q3 2026)",
      "Slack / webhook alerts (Q3 2026)",
      "Team archive (Q3 2026)",
      "Priority support",
    ],
  },
];

const TOOLS_FREE = [
  {
    name: "track_korean_filings",
    blurb: "Real-time DART filings, optionally translated. Same source institutional analysts read.",
  },
  {
    name: "search_korean_industry_news",
    blurb:
      "etnews + 한국경제 RSS classified into 16 industries (semis, batteries, defense, biotech…).",
  },
  {
    name: "lookup_corp_code",
    blurb: "Korean company name → DART corp code. Resolves Hangul or romanized spellings.",
  },
  {
    name: "resolve_stock_code",
    blurb: "KRX 6-digit ticker → DART corp entry. Pairs cleanly with track_korean_filings.",
  },
];

const TOOLS_PAID = [
  {
    name: "monitor_foreign_holders",
    blurb:
      "Foreign 5%-rule filings by BlackRock / Vanguard / Norges / GIC / Temasek / Goldman / JPM + 13 more. Leading indicator of foreign capital flow.",
  },
  {
    name: "monitor_activist_investors",
    blurb:
      "Activist 5%-rule filings auto-tagged for KCGI / Align / Truston / Anda / Cha / VIP / ValueAct / Elliott.",
  },
];

const ROLE_OPTIONS = [
  { value: "", label: "I'm a… (optional)" },
  { value: "analyst", label: "Analyst / fund / SMB research" },
  { value: "rotator", label: "Crypto-native rotator into KRX" },
  { value: "diaspora", label: "Korean-American / overseas Korean" },
  { value: "journalist", label: "Journalist / EM newsletter" },
  { value: "developer", label: "Developer / MCP / agent builder" },
  { value: "other", label: "Other" },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!consent) return;
    try {
      await fetch("/api/notify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, role }),
      });
    } catch {
      // ignore — capture is best-effort here
    }
    setSubmitted(true);
  }

  return (
    <main className="min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <div className="mx-auto max-w-5xl">
        {/* Hero */}
        <header className="flex items-center gap-4">
          {/* SVG inlined to avoid hosting before domain is up */}
          <svg
            viewBox="0 0 64 64"
            className="h-10 w-10"
            aria-hidden="true"
          >
            <rect
              x="0"
              y="0"
              width="64"
              height="64"
              rx="12"
              ry="12"
              fill="#0E1116"
            />
            <polyline
              points="6,32 18,32 22,18 27,46 32,12 37,52 42,28 46,32 58,32"
              stroke="#F0B429"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="text-xl font-semibold tracking-tight">koreanpulse</span>
          <nav className="ml-auto flex gap-5 text-sm text-zinc-400">
            <a href="/today" className="hover:text-zinc-100">today</a>
            <a href="#pricing" className="hover:text-zinc-100">pricing</a>
            <a href="https://github.com/whdrnr2583-cmd/koreanpulse" className="hover:text-zinc-100">github</a>
          </nav>
        </header>

        <section className="mt-16">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/5 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-accent">
            The Korean equity MCP for ChatGPT, Claude.ai, Cursor
          </div>
          <h1 className="text-4xl font-bold leading-tight sm:text-5xl">
            Get pinged in English the moment a 5%-rule filing or DART event hits a stock you care about.
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-zinc-300">
            We watch your KRX tickers in Korean and ping you in English when
            something material moves — foreign-holder 5%-rule disclosures,
            Korean activist filings, major DART events. KRX itself, ASIFMA,
            Wellington, Aberdeen, and Matthews Asia are all on record that the
            English flow off Korean primary sources is structurally inadequate.
            Bloomberg charges $24K/yr and still misses the front page of
            전자신문. We translate, classify, and route the same data into
            your Discord / Telegram / inbox — or call it as MCP tools from
            Claude, Cursor, or your own AI agent.
          </p>
          <p className="mt-4 max-w-2xl text-sm text-zinc-400">
            <strong className="text-zinc-200">1-click connect.</strong> Add{" "}
            <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-accent">
              https://mcp.koreanpulse.dev/mcp
            </code>{" "}
            as a custom connector in ChatGPT or Claude.ai — no{" "}
            <code className="text-xs">npx</code> install, no JSON config, no
            local secrets. Latest MCP Streamable HTTP transport, OAuth-ready,
            actively maintained.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#pricing"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              Join the waitlist →
            </a>
            <a
              href="/today"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              Preview the daily digest
            </a>
          </div>
          <p className="mt-4 text-xs text-zinc-500">
            🚧 Beta — queries + hosted translation are live today; watchlist
            polling and alert dispatch ship Q3 2026. Join the waitlist to lock
            in the launch rate.
          </p>
        </section>

        {/* Timing — recent regulatory inflection makes the audience addressable */}
        <section className="mt-24 rounded-md border border-emerald-800/40 bg-emerald-500/5 p-6">
          <div className="flex items-baseline gap-3">
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
              2026 inflection
            </span>
            <h2 className="text-xl font-semibold">
              Foreign retail just got direct access to KRX
            </h2>
          </div>
          <ul className="mt-4 space-y-2 text-sm text-zinc-300">
            <li>
              <strong className="text-zinc-100">2025-12:</strong> IRC (Investor
              Registration Certificate) abolished — foreign account openings
              accelerated <strong>3–4×</strong>.
            </li>
            <li>
              <strong className="text-zinc-100">2026-04 (last week):</strong>{" "}
              Hana Securities × Futu Securities (3.3M HK fintech retail)
              launched Korean stock trading.
            </li>
            <li>
              <strong className="text-zinc-100">2026-05-04 (yesterday):</strong>{" "}
              Samsung Securities × Interactive Brokers (4.6M global retail)
              pilot launched. Same day: foreigners net-bought a record{" "}
              <strong>3.9 trillion KRW (~$2.7B)</strong> on KOSPI+NXT.
            </li>
            <li>
              <strong className="text-zinc-100">~7.9M foreign retail accounts</strong>{" "}
              now have a wired path into Korean equities — up from ~0 two
              years ago.
            </li>
          </ul>
          <p className="mt-4 text-xs text-zinc-500">
            Sources: FSC, KRX Data, Korea Times, KED Global, 주간한국. The
            English-language data layer for this audience is what koreanpulse
            ships.
          </p>
        </section>

        {/* Why — broadened: institutional gap is the verified anchor */}
        <section className="mt-16">
          <h2 className="text-2xl font-semibold">
            Why people are paying attention to KRX
          </h2>
          <ul className="mt-6 space-y-3 text-zinc-300">
            <li>
              <strong className="text-zinc-100">English IR gap is structural.</strong>{" "}
              KRX itself, ASIFMA, Wellington, Aberdeen, Matthews Asia all on
              record: Korean disclosure flow into English is structurally
              inadequate. We are anchored on this gap.
            </li>
            <li>
              <strong className="text-zinc-100">Real-time on-chain-style disclosures.</strong>{" "}
              DART publishes activist 5% filings, insider trades, and major
              decisions in hours. Closer to a blockchain explorer than to
              quarterly 10-Qs.
            </li>
            <li>
              <strong className="text-zinc-100">MSCI Developed Market reclassification path.</strong>{" "}
              Korea sits on the watchlist. Foreign capital inflow expected if
              upgraded. The mid-curve window opens before the headline trade.
            </li>
            <li>
              <strong className="text-zinc-100">K-themes are global themes.</strong>{" "}
              HBM, EV batteries, K-defense, K-biotech, K-content, shipbuilding —
              same trades you already follow on US tape, with different
              microstructure and faster filings.
            </li>
            <li>
              <strong className="text-zinc-100">Crypto-grade volatility, equity-grade infra.</strong>{" "}
              KOSPI / KOSDAQ small-mid caps move 10–30% on a single filing.
              T+2 settlement, low fees, retail-accessible.
            </li>
          </ul>
        </section>

        {/* How koreanpulse compares — open positioning vs adjacent Korean MCP servers */}
        <section className="mt-20">
          <h2 className="text-2xl font-semibold">How koreanpulse compares</h2>
          <p className="mt-2 max-w-2xl text-sm text-zinc-400">
            There are a handful of Korean-data MCP servers in the wild. Pick the
            one that matches your job. We focus on{" "}
            <strong className="text-zinc-200">
              English-first equity intelligence with named-entity classification,
              served as a hosted endpoint your LLM client can connect to in one
              click.
            </strong>{" "}
            If you need raw KRX OHLCV or Korean-language financial statement
            tables, others do that better.
          </p>

          <div className="mt-6 overflow-x-auto rounded-md border border-zinc-800">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Capability</th>
                  <th className="px-4 py-3 text-left font-semibold">koreanpulse</th>
                  <th className="px-4 py-3 text-left font-semibold">korea-stock-mcp</th>
                  <th className="px-4 py-3 text-left font-semibold">openregistry</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800 text-zinc-300">
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Transport</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Streamable HTTP +
                    SSE (latest MCP spec)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">stdio only (npx install)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Streamable HTTP
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Hosted endpoint</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>{" "}
                    <code className="text-xs">mcp.koreanpulse.dev/mcp</code>
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— (self-install)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>{" "}
                    <code className="text-xs">openregistry.sophymarine.com/mcp</code>
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    1-click connect (ChatGPT / Claude.ai)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Yes
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    No (stdio not supported by remote connectors)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Yes
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Activist filer classification
                    <div className="text-xs font-normal text-zinc-500">
                      KCGI, Align, Truston, Anda, Cha, VIP, Life, Platform,
                      ValueAct, Elliott
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 10+ labels
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— raw filings only</td>
                  <td className="px-4 py-3 text-zinc-500">— registry data only</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Foreign-holder 5%-rule allowlist
                    <div className="text-xs font-normal text-zinc-500">
                      BlackRock, Vanguard, Norges, GIC, Temasek + 16 more
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 21+ labels
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— raw filings only</td>
                  <td className="px-4 py-3 text-zinc-500">— registry data only</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    English-first docstrings (LLM-friendly)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> All tools
                  </td>
                  <td className="px-4 py-3 text-zinc-500">Korean primary, English secondary</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Korean industry news (etnews / 한국경제 RSS, EN translated)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 16 industries
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    KRX OHLCV (daily prices)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— (out of scope)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> KOSPI / KOSDAQ / KONEX
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    XBRL financial statements
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— (out of scope)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Pricing</td>
                  <td className="px-4 py-3">
                    Free 5 tools · Solo $29 · Analyst $79 · Desk $249/mo
                  </td>
                  <td className="px-4 py-3">Free OSS (BYO API keys)</td>
                  <td className="px-4 py-3">Free anonymous tier</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-4 max-w-2xl text-xs text-zinc-500">
            Comparison verified 2026-05-07. Other servers in the space:{" "}
            <a
              href="https://github.com/SongT-50/korean-stock-mcp"
              className="underline hover:text-zinc-300"
            >
              SongT-50/korean-stock-mcp
            </a>
            ,{" "}
            <a
              href="https://github.com/koreal6803/finlab-ai"
              className="underline hover:text-zinc-300"
            >
              koreal6803/finlab-ai
            </a>{" "}
            (quant-focused),{" "}
            <a
              href="https://github.com/eddmpython/dartlab"
              className="underline hover:text-zinc-300"
            >
              eddmpython/dartlab
            </a>{" "}
            (Python lib). The MCP-server space for Korean equities is shaped by
            the underlying data scope, not by any one team — pick what fits your
            workflow.
          </p>
        </section>

        {/* Free public daily snapshot — teaser, not a pricing tier */}
        <section className="mt-20 rounded-md border border-zinc-800 p-6">
          <h2 className="text-2xl font-semibold">Free public daily snapshot</h2>
          <p className="mt-3 text-zinc-300">
            Updated KST 16:30 every weekday at{" "}
            <a href="/today" className="text-accent hover:underline">koreanpulse.dev/today</a>:
            foreign-holder 5%-rule disclosures (BlackRock, Vanguard, Norges, GIC,
            Temasek, Goldman, JPM, Morgan Stanley…), Korean activist filings,
            major DART disclosures — all summarised in English. Public, no
            login. Treat it as a preview of the daily digest paying customers
            get pushed to their channel of choice.
          </p>
          <p className="mt-3 text-sm text-zinc-500">
            Machine-readable JSON at <code>/today.json</code>. Last 30 days at{" "}
            <code>/today/YYYY-MM-DD</code>.
          </p>
        </section>

        {/* Pricing */}
        <section id="pricing" className="mt-20">
          <div className="mb-6 rounded-md border border-amber-700/50 bg-amber-500/5 p-4">
            <div className="flex items-baseline gap-2">
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300">
                🚧 Beta
              </span>
              <span className="text-sm font-medium text-amber-200">
                Solo trial opens Q3 2026
              </span>
            </div>
            <p className="mt-2 text-xs text-zinc-300">
              Queries + hosted translation cache are live today. Watchlist
              polling, alert dispatch, seat enforcement, and per-tier
              retention windows ship Q3 2026. Today the <em>only</em>{" "}
              runtime-enforced difference between tiers is the monthly query
              cap (2K / 15K / 100K). Watchlist counts, alert-channel limits,
              seat caps, and archive retention are paper limits until the
              polling/dispatch loop lands. Join the waitlist and you keep
              the launch rate — no auto-charge until the workflow ships.
            </p>
          </div>
          <h2 className="text-2xl font-semibold">Pricing</h2>
          <p className="mt-2 text-sm text-zinc-400 max-w-2xl">
            Lock-in pricing — early supporters keep the launch rate. Pick the
            tier that matches how many tickers you&apos;ll watch and how many
            channels you&apos;ll want pinged once polling/dispatch ships.
          </p>

          {/* 3b — Free vs Paid comparison box (clarify what subscribing actually unlocks) */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-md border border-zinc-800 p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
                What you get without a license
              </div>
              <div className="mt-1 text-lg font-semibold text-zinc-200">
                5 free MCP tools — raw DART surface
              </div>
              <ul className="mt-3 space-y-1.5 text-sm text-zinc-400">
                <li>· <code>track_korean_filings</code> — raw DART filings, optionally translated</li>
                <li>· <code>lookup_corp_code</code> — Korean name → DART corp code</li>
                <li>· <code>resolve_stock_code</code> — KRX 6-digit ticker → corp entry</li>
                <li>· <code>search_korean_industry_news</code> — etnews / 한국경제 RSS, 16 industries</li>
                <li>· <code>koreanpulse_about</code> — server info, free vs paid tool list</li>
              </ul>
              <p className="mt-3 text-xs text-zinc-500">
                No signup, no API key. Connect via{" "}
                <code>https://mcp.koreanpulse.dev/mcp</code> from ChatGPT or
                Claude.ai and these answer immediately.
              </p>
            </div>
            <div className="rounded-md border border-amber-700/50 bg-amber-500/5 p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-amber-300">
                What Solo $29/mo+ unlocks
              </div>
              <div className="mt-1 text-lg font-semibold text-zinc-100">
                2 paid MCP tools — classification work
              </div>
              <ul className="mt-3 space-y-1.5 text-sm text-zinc-300">
                <li>
                  · <code>monitor_activist_investors</code> — Korean activist
                  filer match (KCGI, Align Partners, Truston, Anda, Cha, VIP,
                  Life, Platform, ValueAct, Elliott)
                </li>
                <li>
                  · <code>monitor_foreign_holders</code> — global allowlist
                  match (BlackRock, Vanguard, Norges, GIC, Temasek, State
                  Street, Fidelity, Capital Group, T. Rowe Price, Wellington,
                  Goldman, JPMorgan, Morgan Stanley, Citadel, Millennium,
                  Bridgewater + others)
                </li>
              </ul>
              <p className="mt-3 text-xs text-zinc-400">
                These two classifications are not derivable from the raw DART
                feed — they require a maintained allowlist + Korean-name
                normalisation + filer-of-record disambiguation. That work is
                what your $29/mo pays for.
              </p>
            </div>
          </div>

          {/* 3e — what the paid gate actually looks like in your AI client (live demo) */}
          <div className="mt-6 rounded-md border border-zinc-800 bg-zinc-950/50 p-5">
            <div className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
              What the paid gate looks like in your AI client (live, 2026-05-07)
            </div>
            <p className="mt-2 text-sm text-zinc-400">
              When a Claude.ai or ChatGPT user asks{" "}
              <em>&quot;what activist filings happened on Samsung Electronics
              this week?&quot;</em> without a Koreanpulse license, the
              hosted endpoint refuses to fall back silently. Claude.ai
              renders this verbatim:
            </p>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded bg-black/60 p-4 text-xs text-zinc-200">
{`I need a Koreanpulse license to identify activist investor filings on
Samsung Electronics.

The monitor_activist_investors tool that identifies known activist
filers (KCGI, Align Partners, Truston, Anda, VIP, Cha, Life, Platform,
ValueAct, Elliott, etc.) is a paid-tier feature ($29/mo Solo plan).
This classification work isn't available from raw DART filings alone.

To subscribe: https://buy.polar.sh/polar_cl_ETpLepEvpGkGBXAOJjQhi7gwizO8GkOW3YaHw4IgHAr

Once you have a license key, I can fetch Samsung Electronics' recent
activist filings from this week. Would you like to sign up?`}
            </pre>
            <p className="mt-3 text-xs text-zinc-500">
              Verified end-to-end against Claude.ai 2026-05-07. ChatGPT
              behaviour varies — its system prompt sometimes routes around
              the gate via web search. For the strongest paid-tool UX, use
              Claude.ai or the OpenAI Responses API directly.
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {PRICING.map((p) => (
              <div
                key={p.name}
                className={
                  p.highlighted
                    ? "rounded-md border border-accent/60 bg-accent/5 p-5"
                    : "rounded-md border border-zinc-800 p-5"
                }
              >
                <div className="text-sm text-zinc-400">{p.name}</div>
                <div className="mt-1 text-2xl font-semibold">{p.price}</div>
                <div className="mt-2 text-xs text-zinc-500">{p.audience}</div>
                <ul className="mt-4 space-y-1.5 text-sm text-zinc-300">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-2">
                      <span className="text-accent">·</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <a
                  href={p.checkoutUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={
                    p.highlighted
                      ? "mt-5 block rounded-md bg-accent px-4 py-2.5 text-center text-sm font-semibold text-ink hover:opacity-90"
                      : "mt-5 block rounded-md border border-accent/60 px-4 py-2.5 text-center text-sm font-semibold text-accent hover:bg-accent/5"
                  }
                >
                  Subscribe to {p.name.replace("Cloud ", "")} {p.price} →
                </a>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-md border border-zinc-800 bg-zinc-950 p-4 text-xs text-zinc-400">
            <p>
              <strong className="text-zinc-200">After subscribing.</strong>{" "}
              Polar emails your license key (format{" "}
              <code className="text-accent">koreanpulse_live_…</code>) to the
              checkout email. Pass it as a tool argument when calling{" "}
              <code className="text-accent">monitor_activist_investors</code> or{" "}
              <code className="text-accent">monitor_foreign_holders</code> in
              Claude.ai, ChatGPT, Cursor, or the OpenAI Responses API — e.g.{" "}
              <code className="text-accent">
                {"{license_key: \"koreanpulse_live_…\", ticker: \"005930\"}"}
              </code>
              . Stdio env-var fallback (
              <code className="text-accent">KOREANPULSE_LICENSE_KEY</code>) and
              one-time HTTP Bearer config ship after the first paid signup;
              for now, include the key per-prompt or in your client&apos;s
              system prompt.
            </p>
          </div>
          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <a
              href="#waitlist"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:bg-zinc-900"
            >
              Or join the waitlist (free)
            </a>
          </div>
          <p className="mt-6 text-xs text-zinc-500">
            Annual billing −20% at launch. Cloud customers still install the
            local MCP (one `pip install` + 4-line Claude Desktop config); the
            Cloudflare Worker holds our OpenAI key and validates your license,
            so no OpenAI key is needed on your side. Enterprise / SLA: contact
            us.
          </p>
          <p className="mt-3 text-xs text-zinc-500">
            By subscribing you agree to our{" "}
            <a href="/terms" className="underline hover:text-zinc-300">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/privacy" className="underline hover:text-zinc-300">
              Privacy Policy
            </a>
            . koreanpulse provides data only —{" "}
            <strong className="text-zinc-300">not investment advice</strong>{" "}
            (자본시장법 §101 면제 영역).
          </p>
        </section>

        {/* Hosted remote MCP — for ChatGPT / Claude.ai / Responses API users */}
        <section className="mt-16 rounded-md border border-zinc-800 p-6">
          <h2 className="text-xl font-semibold">
            Connect from ChatGPT or Claude.ai (no install)
          </h2>
          <p className="mt-3 text-sm text-zinc-300">
            Add the hosted endpoint as a custom connector. The 7 tools (DART
            filings, foreign-holder + activist tracking, Korean industry news)
            return Korean→English translated results in your existing chat —
            no <code>pip install</code>, no local config. Read-only data layer;
            not investment advice.
          </p>
          <div className="mt-4 rounded bg-zinc-900 p-3 font-mono text-sm text-zinc-200 break-all">
            https://mcp.koreanpulse.dev/mcp
          </div>
          <ul className="mt-4 ml-5 list-disc text-sm text-zinc-400 space-y-1">
            <li>
              <strong className="text-zinc-200">ChatGPT</strong> — Settings →
              Connectors → Add custom connector → paste URL. Authentication:
              None.
            </li>
            <li>
              <strong className="text-zinc-200">Claude.ai</strong> — Settings →
              Connectors → Add custom connector → paste URL.
            </li>
            <li>
              <strong className="text-zinc-200">OpenAI Responses API</strong>{" "}
              — <code>{`tools=[{type: "mcp", server_url: "https://mcp.koreanpulse.dev/mcp"}]`}</code>
            </li>
          </ul>
          <p className="mt-3 text-xs text-zinc-500">
            Streamable HTTP transport (single-region node, Let&apos;s Encrypt
            cert). Validated end-to-end against ChatGPT and Claude.ai 2026-05-06.
            For max privacy or self-hosting, the local stdio path below is
            still canonical.
          </p>
        </section>

        {/* Run it yourself (OSS) — separate, below pricing */}
        <section className="mt-8 rounded-md border border-zinc-800 p-6">
          <h2 className="text-xl font-semibold">Run it yourself (OSS)</h2>
          <p className="mt-3 text-sm text-zinc-300">
            Source is AGPL-3.0. Self-hosters can run the MCP server locally
            with their own DART and OpenAI keys — community support only, no
            hosted archive, no shared translation cache, no alerts. This path
            is for hackers and max-privacy users; the paid Cloud tiers above
            are what designed to ship you the watchlist-to-alert workflow once
            polling/dispatch lands (Q3 2026).
          </p>
          <div className="mt-4 flex gap-3">
            <a
              href="https://github.com/whdrnr2583-cmd/koreanpulse"
              className="rounded-md border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              View on GitHub
            </a>
            <a
              href="https://github.com/whdrnr2583-cmd/koreanpulse/blob/main/docs/SELF_HOSTING.md"
              className="rounded-md border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              Self-hosting guide
            </a>
          </div>
        </section>

        {/* What runs under the hood — MCP tools moved below pricing */}
        <section className="mt-16">
          <h2 className="text-xl font-semibold">What runs under the hood</h2>
          <p className="mt-3 text-zinc-400 text-sm max-w-2xl">
            7 MCP tools split into <strong className="text-zinc-200">5 free</strong> (raw
            DART + RSS surface, no signup) and{" "}
            <strong className="text-zinc-200">2 paid</strong> — the
            classification work that takes a Korean speaker by hand
            (5%-rule foreign-holder + Korean activist filer matching).
            ChatGPT and Claude.ai render the inline subscription link
            automatically when a paid tool is called without a license.
          </p>

          <h3 className="mt-8 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Free (no signup)
          </h3>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {TOOLS_FREE.map((t) => (
              <div
                key={t.name}
                className="rounded-md border border-zinc-800 p-4"
              >
                <code className="text-sm text-accent">{t.name}</code>
                <p className="mt-2 text-sm text-zinc-300">{t.blurb}</p>
              </div>
            ))}
          </div>

          <h3 className="mt-8 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Paid (Solo $29/mo or higher)
          </h3>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {TOOLS_PAID.map((t) => (
              <div
                key={t.name}
                className="rounded-md border border-amber-700/40 bg-amber-950/10 p-4"
              >
                <code className="text-sm text-accent">{t.name}</code>
                <p className="mt-2 text-sm text-zinc-300">{t.blurb}</p>
              </div>
            ))}
          </div>

          <p className="mt-4 text-sm text-zinc-500">
            More shipping: <code>summarize_korean_earnings_call</code>,{" "}
            <code>get_ma_pipeline</code>, <code>track_government_policy</code>,
            and webhook alert delivery (Discord / Telegram / Slack).
          </p>
        </section>

        {/* Email capture with role */}
        <section id="waitlist" className="mt-20 scroll-mt-20">
          <h2 className="text-2xl font-semibold">Get notified at launch</h2>
          <p className="mt-2 text-sm text-zinc-400">
            One email when the Solo trial opens and the marketplaces accept us.
            The role field is optional — it helps us figure out who&apos;s
            actually showing up.
          </p>
          <form
            onSubmit={onSubmit}
            className="mt-4 flex max-w-md flex-col gap-2"
          >
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@somefund.xyz"
              className="rounded-md border border-zinc-700 bg-transparent px-3 py-2 text-sm placeholder:text-zinc-500 focus:border-accent focus:outline-none"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded-md border border-zinc-700 bg-transparent px-3 py-2 text-sm text-zinc-300 focus:border-accent focus:outline-none"
            >
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-ink">
                  {opt.label}
                </option>
              ))}
            </select>
            <label className="flex items-start gap-2 text-xs text-zinc-400">
              <input
                type="checkbox"
                required
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5 accent-accent"
              />
              <span>
                I agree to the{" "}
                <a href="/privacy" className="underline hover:text-zinc-200">
                  Privacy Policy
                </a>{" "}
                and consent to receive a single launch email. I understand I
                can unsubscribe at any time.
              </span>
            </label>
            <button
              type="submit"
              disabled={!consent}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Notify me when Solo trial opens
            </button>
          </form>
          {submitted && (
            <p className="mt-3 text-sm text-accent">
              Got it. You&apos;ll hear from us once.
            </p>
          )}
        </section>

        {/* Disclaimer — not investment advice */}
        <section className="mt-16 rounded-md border border-zinc-800 bg-zinc-900/40 p-5 text-xs text-zinc-400">
          <p className="font-semibold text-zinc-300">Not investment advice.</p>
          <p className="mt-2 leading-relaxed">
            koreanpulse provides translated and classified primary-source
            data from Korean public filings (DART) and Korean industry news.
            It is not investment advice and does not constitute a
            recommendation to buy, sell, or hold any security. The service
            performs no individualized analysis or personalized
            recommendation. All output is general data routing intended for
            informational purposes only. You are responsible for your own
            investment decisions and should consult a licensed financial
            advisor where appropriate.
          </p>
          <p className="mt-2 leading-relaxed text-zinc-500">
            koreanpulse는 한국 공시시스템(DART) 및 한국 산업 뉴스의 1차
            자료를 영어로 번역·분류하여 제공하는 데이터 서비스이며,
            투자자문 또는 투자권유에 해당하지 않습니다.
          </p>
        </section>

        <footer className="mt-12 text-xs text-zinc-500">
          <span>© koreanpulse · </span>
          <a
            href="https://github.com/whdrnr2583-cmd/koreanpulse"
            className="underline hover:text-zinc-300"
          >
            GitHub
          </a>
          <span> · </span>
          <a href="/today.json" className="underline hover:text-zinc-300">
            JSON
          </a>
          <span> · </span>
          <a href="/privacy" className="underline hover:text-zinc-300">
            Privacy
          </a>
          <span> · </span>
          <a href="/terms" className="underline hover:text-zinc-300">
            Terms
          </a>
          <span> · AGPL source / commercial hosted</span>
        </footer>
      </div>
    </main>
  );
}
