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
      "~2,000 queries/mo (available now)",
      "5 watchlists (planned — not yet available)",
      "30-day archive search (planned — not yet available)",
      "1 Discord or Telegram alert channel (planned — not yet available)",
      "Daily English digest (available now)",
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
      "~15,000 queries/mo (available now)",
      "25 watchlists (planned — not yet available)",
      "1-year archive search (planned — not yet available)",
      "Multi-channel alerts (Discord / Telegram / Email) (planned — not yet available)",
      "Saved searches (planned — not yet available)",
      "CSV / JSON export (planned — not yet available)",
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
      "~100,000 queries/mo (available now)",
      "3 seats, shared watchlists (planned — not yet available)",
      "Slack / webhook alerts (planned — not yet available)",
      "Team archive (planned — not yet available)",
      "Priority support",
    ],
  },
];

const TOOLS_FREE = [
  {
    name: "track_korean_filings",
    blurb: "DART filings as disclosed, optionally translated to English. Every item links to the original filing.",
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
  {
    name: "koreanpulse_about",
    blurb: "Server self-description — tool catalog, free vs license-gated split, data sources.",
  },
];

const TOOLS_PAID = [
  {
    name: "monitor_foreign_holders",
    blurb:
      "Foreign 5%-rule filings tagged against a maintained list — BlackRock / Vanguard / Norges / GIC / Temasek / Goldman / JPM + 13 more.",
  },
  {
    name: "monitor_activist_investors",
    blurb:
      "Activist 5%-rule filings auto-tagged for KCGI / Align / Anda / Cha / Truston / Life / Platform / VIP, plus international ValueAct + Elliott.",
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
  const [formState, setFormState] = useState<"idle" | "submitting" | "success" | "error">("idle");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!consent || formState === "submitting") return;
    setFormState("submitting");
    try {
      const res = await fetch("/api/notify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, role, consent }),
      });
      const data = (await res.json().catch(() => ({}))) as { ok?: boolean };
      // Success is only shown once the server confirms the signup was stored.
      setFormState(res.ok && data.ok === true ? "success" : "error");
    } catch {
      setFormState("error");
    }
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
            Hosted MCP — activist &amp; foreign-holder filing tagging for KRX
          </div>
          <h1 className="text-4xl font-bold leading-tight sm:text-5xl">
            When KCGI or Elliott files a 5%-rule disclosure on a Korean stock, your AI assistant sees it in English — tagged, not raw.
          </h1>
          <p className="mt-5 max-w-2xl text-base font-medium text-zinc-200">
            koreanpulse is a hosted MCP server that tags Korean DART
            filings by known activist investors (KCGI, Align Partners, Elliott,
            ValueAct, Truston, Anda, Cha, VIP…) and global foreign holders
            (BlackRock, Vanguard, Norges Bank, GIC, Temasek…) — translated
            to English, callable from Claude.ai, ChatGPT, or Cursor in
            one click.
          </p>
          <p className="mt-4 max-w-2xl text-zinc-300">
            DART publishes activist 5% disclosures in hours, but the raw feed
            is Korean text with no entity tagging. Identifying whether a filing
            is KCGI or a passive retail holder requires a maintained Korean-name
            allowlist and filer-of-record disambiguation that the raw API does
            not provide. That classification is what koreanpulse ships.
          </p>
          <p className="mt-4 max-w-2xl text-zinc-300">
            The same endpoint also surfaces foreign 5%-rule entries whose
            filer matches a maintained list of sovereign wealth funds, global
            asset managers, and hedge funds. koreanpulse translates, tags,
            and filters the primary-source DART feed and links every item to
            the original filing — inside your AI workflow.
          </p>
          <p className="mt-4 max-w-2xl text-sm text-zinc-400">
            <strong className="text-zinc-200">1-click connect.</strong> Add{" "}
            <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-accent">
              https://mcp.koreanpulse.dev/mcp
            </code>{" "}
            as a custom connector in ChatGPT or Claude.ai — no{" "}
            <code className="text-xs">npx</code> install, no JSON config, no
            local secrets, no DART API key needed for the 5 free tools.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#pricing"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              Subscribe — Solo $29/mo →
            </a>
            <a
              href="/today"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              See today&apos;s classified filings
            </a>
          </div>
          <p className="mt-4 text-xs text-zinc-500">
            Beta — activist + foreign-holder tagging and DART queries work
            now. Watchlist polling and alert dispatch are planned and not yet
            available.
          </p>
        </section>

        {/* Activist filing scenario — concrete ICP moment */}
        <section className="mt-16 rounded-md border border-amber-700/50 bg-amber-500/5 p-6">
          <div className="flex items-baseline gap-3">
            <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300">
              What this looks like in practice
            </span>
          </div>
          <p className="mt-3 text-sm text-zinc-300">
            Two real 5%-rule filings from July 2026, exactly as the
            classifier tags them (verify both on DART via the receipt
            numbers):
          </p>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded bg-black/60 p-4 text-xs text-zinc-200">
{`1. Hanyang Securities 한양증권 (001750)
   Filer: 케이씨지아이제2호사모투자 → tagged ACTIVIST — KCGI
   Type:  주식등의대량보유상황보고서(일반)
          → "Report on Large Holdings of Stocks, Etc. (General)"
   Filed: 2026-07-15 | DART receipt 20260715000397
   https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260715000397

2. Coway 코웨이 (021240)
   Filer: 얼라인파트너스자산운용 → tagged ACTIVIST — Align Partners
   Type:  주식등의대량보유상황보고서(일반)
   Filed: 2026-07-07 | DART receipt 20260707000434
   https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260707000434

Every 5%-rule filer — passive fund, individual, or activist — uses this
same DART filing type, and the raw feed names the filer in Korean
free text only. koreanpulse tags the filer against a maintained
allowlist of named funds; filers not on the list are left untagged,
never guessed.`}
          </pre>
          <p className="mt-3 text-xs text-zinc-500">
            Real filings, reproducible with{" "}
            <code className="text-zinc-400">monitor_activist_investors</code>{" "}
            (allowlist matching on the filer of record). Company names
            translated automatically. Not investment advice.
          </p>
        </section>

        {/* Timing — recent regulatory inflection makes the audience addressable */}
        <section className="mt-12 rounded-md border border-emerald-800/40 bg-emerald-500/5 p-6">
          <div className="flex items-baseline gap-3">
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">
              Why now
            </span>
            <h2 className="text-xl font-semibold">
              Foreign access to KRX keeps getting easier
            </h2>
          </div>
          <ul className="mt-4 space-y-2 text-sm text-zinc-300">
            <li>
              <strong className="text-zinc-100">2023-12-14:</strong> the
              Investor Registration Certificate (IRC) requirement for foreign
              investors was abolished, removing the decades-old registration
              step for direct KRX access.
            </li>
            <li>
              <strong className="text-zinc-100">2026-04:</strong> Hana
              Securities and Futu Securities launched Korean stock trading for
              Futu&apos;s Hong Kong retail customers.
            </li>
            <li>
              <strong className="text-zinc-100">2026-05:</strong> Samsung
              Securities and Interactive Brokers launched a Korean stock
              trading pilot for IBKR customers.
            </li>
          </ul>
          <p className="mt-4 text-xs text-zinc-500">
            More foreign investors can reach KRX directly, while the primary
            disclosure source (DART) remains Korean-only. That English-language
            gap is what koreanpulse works on.
          </p>
        </section>

        {/* Why — broadened: institutional gap is the verified anchor */}
        <section className="mt-16">
          <h2 className="text-2xl font-semibold">
            Why people are paying attention to KRX
          </h2>
          <ul className="mt-6 space-y-3 text-zinc-300">
            <li>
              <strong className="text-zinc-100">The activist signal is in the filing, but the entity is not.</strong>{" "}
              DART 5%-rule filings name the filer in Korean only. Whether
              &ldquo;국내투자자&rdquo; is KCGI building a position or a retail
              investor crossing a reporting threshold is not labelled anywhere
              in the raw feed. koreanpulse maintains the allowlist and
              disambiguates on every pull.
            </li>
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
              Korea has been under review for reclassification — one of the
              reasons global investors track Korean market-access changes.
            </li>
            <li>
              <strong className="text-zinc-100">K-themes are global themes.</strong>{" "}
              HBM, EV batteries, K-defense, K-biotech, K-content, shipbuilding —
              same trades you already follow on US tape, with different
              microstructure and faster filings.
            </li>
            <li>
              <strong className="text-zinc-100">Disclosure-driven market.</strong>{" "}
              Korean small/mid caps are heavily covered by retail flow that
              reacts to DART disclosures — reading the filing itself, fast,
              matters more here than in most markets.
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
              English-first equity data with allowlist-based filer tagging,
              served as a hosted endpoint your LLM client can connect to in one
              click.
            </strong>{" "}
            If you need raw KRX OHLCV or Korean-language financial statement
            tables, others do that better.
          </p>

          <div className="mt-6 overflow-x-auto rounded-md border border-zinc-800">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Capability</th>
                  <th className="px-4 py-3 text-left font-semibold">koreanpulse</th>
                  <th className="px-4 py-3 text-left font-semibold">
                    korea-stock-mcp
                    <div className="font-normal normal-case text-zinc-500">jjlabsio</div>
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    korean-dart-mcp
                    <div className="font-normal normal-case text-zinc-500">chrisryugj</div>
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">openregistry</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800 text-zinc-300">
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Transport</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Streamable HTTP +
                    SSE
                  </td>
                  <td className="px-4 py-3 text-zinc-500">stdio only (npx)</td>
                  <td className="px-4 py-3 text-zinc-500">stdio only (npx)</td>
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
                  <td className="px-4 py-3 text-zinc-500">— (self-install)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>{" "}
                    <code className="text-xs">openregistry.sophymarine.com</code>
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    1-click connect (ChatGPT / Claude.ai)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Yes
                  </td>
                  <td className="px-4 py-3 text-zinc-500">No (stdio)</td>
                  <td className="px-4 py-3 text-zinc-500">No (stdio)</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Yes
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Activist filer tagging (allowlist)
                    <div className="text-xs font-normal text-zinc-500">
                      KCGI, Align, Truston, Anda, Cha, VIP, Life, Platform,
                      Must, Dalton, FCP, Oasis, Palliser, Whitebox, City of
                      London, ValueAct, Elliott
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 17 labels
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— raw filings only</td>
                  <td className="px-4 py-3 text-zinc-500">— raw filings only</td>
                  <td className="px-4 py-3 text-zinc-500">— registry data only</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Foreign-holder 5%-rule allowlist
                    <div className="text-xs font-normal text-zinc-500">
                      BlackRock, Vanguard, Norges, GIC, Temasek + 15 more
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 20 labels
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— raw filings only</td>
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
                  <td className="px-4 py-3 text-zinc-500">Korean primary</td>
                  <td className="px-4 py-3 text-zinc-500">Korean primary</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Korean→English translation inside tool responses
                    <div className="text-xs font-normal text-zinc-500">
                      filing titles + company names translated in the returned
                      data, not just in the docs
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Hosted
                    translation cache
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    — data returned in Korean
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    — data returned in Korean
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— registry data only</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Correction-filing linkage
                    <div className="text-xs font-normal text-zinc-500">
                      정정공시 tagged and linked back to the filing it corrects
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>{" "}
                    <code className="text-xs">is_correction</code> +{" "}
                    <code className="text-xs">previous_receipt_no</code> fields
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— not linked</td>
                  <td className="px-4 py-3 text-zinc-500">— not linked</td>
                  <td className="px-4 py-3 text-zinc-500">— registry data only</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Korean industry news (etnews / 한국경제 / Korea Herald /
                    ZDNet Korea RSS, EN)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> 16 industries
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    KRX OHLCV (daily prices)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— out of scope</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> KOSPI / KOSDAQ
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    XBRL financial statements
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— out of scope</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    HWP / PDF attachment → markdown
                  </td>
                  <td className="px-4 py-3 text-zinc-500">— out of scope</td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-500">—</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    Multi-user architecture
                    <div className="text-xs font-normal text-zinc-500">
                      One endpoint, N AI agents in parallel
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> N→1 hosted
                    (one shared DART key, cached)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    1:1 (one process per user on user&apos;s machine)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    1:1 (one process per user on user&apos;s machine)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-emerald-400">✓</span> Hosted
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">
                    DART API key required from end user
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    No (free tools use our shared key)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-amber-400">Yes</span> (each user signs up)
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-amber-400">Yes</span> (each user signs up)
                  </td>
                  <td className="px-4 py-3 text-zinc-500">
                    No
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Pricing</td>
                  <td className="px-4 py-3">
                    Free 5 tools · Solo $29 · Analyst $79 · Desk $249/mo
                  </td>
                  <td className="px-4 py-3">Free OSS (BYO API keys)</td>
                  <td className="px-4 py-3">Free OSS (BYO API keys)</td>
                  <td className="px-4 py-3">Free anonymous tier</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-4 max-w-2xl text-xs text-zinc-500">
            Comparison last verified 2026-07-19 — other projects may have
            shipped changes since. Other servers in the space:{" "}
            <a
              href="https://github.com/OldTemple91/korea-filings-api"
              className="underline hover:text-zinc-300"
            >
              OldTemple91/korea-filings-api
            </a>{" "}
            (English summaries, pay-per-call),{" "}
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

          <p className="mt-4 max-w-2xl text-sm text-zinc-400">
            <strong className="text-zinc-200">
              Where official English disclosure ends.
            </strong>{" "}
            KRX&apos;s mandatory English-disclosure regime reaches only the
            largest listed issuers; most KOSDAQ and small/mid-cap filings have
            no official English version. koreanpulse translates the DART feed
            itself, so English coverage does not stop where the mandate does.
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
            login. The page shows its data date and flags itself when a
            snapshot is stale.
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
                Beta — what works now vs. what is planned
              </span>
            </div>
            <div className="mt-3 grid gap-4 text-xs text-zinc-300 sm:grid-cols-2">
              <div>
                <p className="font-semibold text-emerald-300">Available now</p>
                <ul className="mt-1.5 list-disc space-y-1 pl-4">
                  <li>Hosted remote MCP endpoint (<code>mcp.koreanpulse.dev/mcp</code>)</li>
                  <li>5 free tools: DART filings, company/ticker resolution, industry news, server info</li>
                  <li>2 license-gated tools: <code>monitor_activist_investors</code>, <code>monitor_foreign_holders</code></li>
                  <li>Hosted English translation for filing titles</li>
                  <li>Public daily snapshot at <a href="/today" className="underline">/today</a></li>
                </ul>
              </div>
              <div>
                <p className="font-semibold text-amber-300">Not yet available (planned)</p>
                <ul className="mt-1.5 list-disc space-y-1 pl-4">
                  <li>Continuous watchlist polling</li>
                  <li>Discord / Telegram / Email / Slack alerts</li>
                  <li>Saved searches, CSV/JSON export</li>
                  <li>Archive search &amp; retention windows</li>
                  <li>Team seats &amp; shared watchlists</li>
                </ul>
              </div>
            </div>
            <p className="mt-3 text-xs text-zinc-400">
              Until the planned features ship, the runtime differences between
              paid tiers are the monthly query cap (2K / 15K / 100K) and
              support level — most tier differentiation is roadmap. If a
              planned feature matters to you, wait for it to ship before
              subscribing, or ask us first.
            </p>
          </div>
          <h2 className="text-2xl font-semibold">Pricing</h2>
          <p className="mt-2 text-sm text-zinc-400 max-w-2xl">
            Solo $29/mo unlocks the two allowlist-tagging tools (activist +
            foreign-holder) now. Subscribing via Polar starts a paid monthly
            subscription that charges immediately at checkout. Watchlist
            polling and alert dispatch are planned and not yet available —
            early subscribers keep their signup rate when those features land.
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
                  Life, Platform, Must, Dalton, FCP, Oasis, Palliser,
                  Whitebox, City of London, ValueAct, Elliott)
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
              What the license gate returns without a key
            </div>
            <p className="mt-2 text-sm text-zinc-400">
              Calling a license-gated tool without a <code>license_key</code>{" "}
              never fails silently — the tool returns this notice, which your
              AI client relays:
            </p>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded bg-black/60 p-4 text-xs text-zinc-200">
{`\`monitor_activist_investors\` requires a license key. Pass a
\`license_key\` argument when calling this tool. The activist /
foreign-holder allowlist tagging runs server-side on the hosted
koreanpulse service. OSS self-host (github.com/whdrnr2583-cmd/
koreanpulse + your own DART API key) is free but does NOT include
this allowlist tagging, so self-hosting will not unlock this tool.`}
            </pre>
            <p className="mt-3 text-xs text-zinc-500">
              How the surrounding assistant text reads varies by client and
              model. Your license key arrives by email after checkout.
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
              <code className="text-accent">kp_…</code>) to the
              checkout email. Pass it as a tool argument when calling{" "}
              <code className="text-accent">monitor_activist_investors</code> or{" "}
              <code className="text-accent">monitor_foreign_holders</code> in
              Claude.ai, ChatGPT, Cursor, or the OpenAI Responses API — e.g.{" "}
              <code className="text-accent">
                {"{license_key: \"kp_…\", ticker: \"005930\"}"}
              </code>
              . A stdio env-var option and one-time HTTP Bearer config are
              planned but not yet available; for now, include the key
              per-prompt or in your client&apos;s system prompt.
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
            Cloud licenses work on the hosted endpoint (no install) or with
            the local stdio install; hosted translation uses our OpenAI key
            and validates your license, so no OpenAI key is needed on your
            side. Enterprise / SLA: contact us.
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
            . koreanpulse provides disclosure data, translation, filtering,
            and tagging only —{" "}
            <strong className="text-zinc-300">not investment advice</strong>.
            It does not execute trades or provide personalized buy/sell
            recommendations.
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
            cert). Last validated end-to-end against ChatGPT and Claude.ai on
            2026-05-06. For max privacy or self-hosting, the local stdio path
            below is still canonical.
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
            are where the planned watchlist-to-alert workflow will land once
            polling and dispatch ship.
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
            <strong className="text-zinc-200">2 license-gated</strong> —
            5%-rule foreign-holder and Korean activist filer matching against
            a maintained allowlist. Calling a gated tool without a license
            returns a clear license-required notice (shown above), never a
            silent failure.
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
            Planned, not yet available:{" "}
            <code>summarize_korean_earnings_call</code>,{" "}
            <code>get_ma_pipeline</code>, <code>track_government_policy</code>,
            and webhook alert delivery (Discord / Telegram / Slack).
          </p>
        </section>

        {/* Email capture with role */}
        <section id="waitlist" className="mt-20 scroll-mt-20">
          <h2 className="text-2xl font-semibold">Get notified at launch</h2>
          <p className="mt-2 text-sm text-zinc-400">
            One email when the planned watchlist-alert workflow ships. The
            role field is optional — it helps us figure out who&apos;s
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
              disabled={!consent || formState === "submitting"}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {formState === "submitting" ? "Saving…" : "Notify me at launch"}
            </button>
          </form>
          {formState === "success" && (
            <p className="mt-3 text-sm text-accent">
              Got it. You&apos;ll hear from us once.
            </p>
          )}
          {formState === "error" && (
            <p className="mt-3 text-sm text-red-400">
              We couldn&apos;t save your signup — please check the email address
              and try again in a moment.
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

        {/* Guides — internal links so the GEO content is crawlable from home */}
        <section className="mt-16 border-t border-zinc-800 pt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Guides
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-zinc-300">
            <li>
              <a
                href="/track-korean-dart-filings-with-ai"
                className="text-accent hover:underline"
              >
                How to track Korean DART filings with an AI assistant
              </a>{" "}
              — what DART is, which filings carry signal, and how to wire an
              MCP server into ChatGPT, Claude, or Cursor.
            </li>
            <li>
              <a
                href="/korean-stock-filings-in-english"
                className="text-accent hover:underline"
              >
                How to get Korean stock filings (DART) in English
              </a>{" "}
              — four ways to access KOSPI/KOSDAQ disclosures in English,
              compared.
            </li>
            <li>
              <a
                href="/best-korean-stock-mcp-server"
                className="text-accent hover:underline"
              >
                The best MCP server for Korean stocks, compared
              </a>{" "}
              — self-hosted OpenDART wrappers, English-summary servers, and
              the hosted koreanpulse endpoint, compared honestly.
            </li>
            <li>
              <a
                href="/track-foreign-investors-activists-korea"
                className="text-accent hover:underline"
              >
                How to track foreign investors and activists in Korean stocks
              </a>{" "}
              — the 5%-rule disclosure, who the major foreign holders and
              activists are, and how to monitor their filings from an AI
              assistant.
            </li>
            <li>
              <a
                href="/monitor-korean-governance-foreign-holders"
                className="text-accent hover:underline"
              >
                How to monitor Korean corporate governance disclosures and
                foreign institutional holders
              </a>{" "}
              — governance/distress red-flag tags on every DART filing, plus
              tracking foreign institutional 5%-rule holders in English.
            </li>
          </ul>
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
