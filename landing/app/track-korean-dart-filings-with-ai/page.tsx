import type { Metadata } from "next";

const SITE = "https://koreanpulse.dev";
const PAGE_URL = `${SITE}/track-korean-dart-filings-with-ai`;
const DESC =
  "A practical guide to tracking Korean DART (전자공시) corporate filings from " +
  "inside an AI assistant. What DART is, which filings matter, how to wire an " +
  "MCP server into ChatGPT or Claude, and the prompts that work.";

export const metadata: Metadata = {
  title: "How to track Korean DART filings with an AI assistant | koreanpulse",
  description: DESC,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "How to track Korean DART filings with an AI assistant",
    description: DESC,
    type: "article",
    url: PAGE_URL,
    siteName: "koreanpulse",
  },
};

const articleLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "How to track Korean DART filings with an AI assistant",
  description: DESC,
  url: PAGE_URL,
  about: [
    "DART filings",
    "Korean stock market",
    "MCP server",
    "AI assistant",
    "KOSPI",
    "KOSDAQ",
  ],
  publisher: { "@type": "Organization", name: "koreanpulse", url: SITE },
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "What is DART?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "DART (전자공시시스템) is South Korea's electronic corporate disclosure " +
          "system, operated by the Financial Supervisory Service. It is the " +
          "canonical, real-time, free source for every KOSPI, KOSDAQ, and KONEX " +
          "filing — 5%-rule shareholding disclosures, M&A, capital raises, and " +
          "periodic reports. Its primary interface and an OpenAPI are Korean-only.",
      },
    },
    {
      "@type": "Question",
      name: "Can ChatGPT or Claude read Korean DART filings?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Not on their own — DART is not in a model's training data in any " +
          "real-time form, and general web search rarely surfaces individual " +
          "filings. Connecting an MCP server that wraps the DART OpenAPI gives " +
          "the assistant typed tools it can call to fetch and translate filings " +
          "directly inside the chat.",
      },
    },
    {
      "@type": "Question",
      name: "Is a DART API key required?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "The DART OpenAPI itself requires a free key from opendart.fss.or.kr " +
          "(40,000 calls/day). If you connect koreanpulse's hosted endpoint, the " +
          "free filing tools use a shared key, so you do not need to register " +
          "your own. Self-hosting the open-source server requires your own key.",
      },
    },
  ],
};

export default function TrackDartWithAiGuide() {
  return (
    <main className="min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
      />
      <div className="mx-auto max-w-3xl">
        <header className="flex items-center gap-2 text-sm text-zinc-400">
          <a href="/" className="font-semibold text-zinc-200 hover:text-zinc-100">
            koreanpulse
          </a>
          <span>/</span>
          <span>Track Korean DART filings with an AI assistant</span>
        </header>

        <article className="mt-10">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            How to track Korean DART filings with an AI assistant
          </h1>

          <p className="mt-6 text-lg text-zinc-300">
            If you research Korean equities, the filing you most want to see
            first is almost always in <strong className="text-zinc-100">DART</strong>{" "}
            — and almost always in Korean. This guide explains what DART is,
            which filings carry signal, and how to wire it into an AI assistant
            (ChatGPT, Claude, or Cursor) so you can ask{" "}
            <em>&ldquo;what did Samsung Electronics file this week?&rdquo;</em>{" "}
            in plain English and get a real answer.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">What DART is</h2>
          <p className="mt-4 text-zinc-300">
            <strong className="text-zinc-100">DART</strong> (전자공시시스템,
            &ldquo;Data Analysis, Retrieval and Transfer System&rdquo;) is South
            Korea&apos;s electronic corporate disclosure system, run by the
            Financial Supervisory Service. Every company listed on KOSPI,
            KOSDAQ, or KONEX files here. It is the canonical, real-time, free
            primary source — the Korean equivalent of the SEC&apos;s EDGAR.
          </p>
          <p className="mt-4 text-zinc-300">
            DART also publishes an{" "}
            <a
              href="https://opendart.fss.or.kr/"
              className="text-accent hover:underline"
              rel="noopener noreferrer"
            >
              OpenAPI
            </a>{" "}
            (free key, 40,000 calls/day). The catch for non-Korean readers: the
            DART site, the filing titles, and the API field values are all in
            Korean. There is no official English mode. An investor who reads
            Korean works from the primary source; everyone else works from a
            translation that is, by the on-record admission of KRX itself,
            ASIFMA, Wellington, Aberdeen, and Matthews Asia, structurally late
            or absent.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Which DART filings actually carry signal
          </h2>
          <p className="mt-4 text-zinc-300">
            DART is high-volume — hundreds of filings a day. Four categories do
            most of the work:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">5%-rule disclosures</strong>{" "}
              (주식등의대량보유상황보고서) — filed when an investor crosses 5%
              ownership of a listed company, or shifts an existing holding by
              1% or more. This is the single most-watched filing type: it is
              the leading indicator of foreign capital entering a name and of
              activist accumulation.
            </li>
            <li>
              <strong className="text-zinc-100">Major business events</strong>{" "}
              (주요사항보고서) — M&amp;A, spin-offs, capital raises,
              convertible-bond issuance, large supply contracts.
            </li>
            <li>
              <strong className="text-zinc-100">Periodic reports</strong>{" "}
              (정기공시) — annual, half-year, and quarterly reports.
            </li>
            <li>
              <strong className="text-zinc-100">
                Issuance &amp; insider filings
              </strong>{" "}
              — new share issuance, treasury-stock decisions, and
              executive/major-shareholder trading reports.
            </li>
          </ul>
          <p className="mt-4 text-zinc-300">
            DART tags each filing with a one-letter type code (A = periodic,
            B = major event, C = issuance, D = shareholding, F = audit, and
            so on), which is useful for filtering once you are calling the API
            programmatically.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Why an AI assistant can&apos;t do this out of the box
          </h2>
          <p className="mt-4 text-zinc-300">
            It is reasonable to expect ChatGPT or Claude to just answer
            &ldquo;any new filings on SK hynix?&rdquo; They cannot, for two
            structural reasons:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">
                Filings are not in the model&apos;s training data.
              </strong>{" "}
              A language model&apos;s knowledge is frozen at its training
              cutoff and was never a real-time feed of individual DART
              receipts. Today&apos;s 5%-rule filing did not exist when the
              model was trained.
            </li>
            <li>
              <strong className="text-zinc-100">
                Web search rarely surfaces a specific filing.
              </strong>{" "}
              General web search finds news <em>about</em> a filing, hours
              later and often without the underlying receipt number, filer
              name, or exact stake. It does not reliably reach the DART
              primary source.
            </li>
          </ul>
          <p className="mt-4 text-zinc-300">
            The fix is to give the assistant a <strong className="text-zinc-100">tool</strong>{" "}
            it can call. That is what the Model Context Protocol (MCP) is for:
            an MCP server wraps an external data source (here, the DART
            OpenAPI) and exposes it as typed functions the assistant invokes
            on demand. When you ask about a Korean filing, the assistant calls
            the tool, the tool queries DART, and the result comes back into
            the chat — translated, if the server does translation.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Three ways to track DART filings from an AI assistant
          </h2>
          <ol className="mt-4 space-y-3 text-zinc-300">
            <li>
              <strong className="text-zinc-100">
                1. Build your own MCP server over the DART OpenAPI.
              </strong>{" "}
              Register a free key at opendart.fss.or.kr, wrap the{" "}
              <code className="text-accent">list</code> and{" "}
              <code className="text-accent">document</code> endpoints in an
              MCP server (the{" "}
              <a
                href="https://modelcontextprotocol.io/"
                className="text-accent hover:underline"
                rel="noopener noreferrer"
              >
                MCP SDK
              </a>{" "}
              has Python and TypeScript libraries), and add a translation step.
              Full control; it is real work, and you maintain the Korean
              company-name index and quota handling yourself.
            </li>
            <li>
              <strong className="text-zinc-100">
                2. Use an existing Korean-data MCP server.
              </strong>{" "}
              Several open-source MCP servers wrap DART. Most are stdio-only
              (you run them locally with your own key) and return filings in
              Korean. Good if you read Korean and want raw data.
            </li>
            <li>
              <strong className="text-zinc-100">
                3. Connect a hosted Korean stock market MCP server.
              </strong>{" "}
              A hosted endpoint means no local install and no key wrangling —
              you add one URL as a custom connector. koreanpulse (below) is
              one such server; it also does the English translation and
              filer classification, which is the part that otherwise takes a
              Korean speaker by hand.
            </li>
          </ol>

          <h2 className="mt-12 text-2xl font-semibold">
            Wiring koreanpulse into your assistant
          </h2>
          <p className="mt-4 text-zinc-300">
            <a href="/" className="text-accent hover:underline">
              koreanpulse
            </a>{" "}
            is a Korean stock market intelligence MCP server. It wraps the DART
            OpenAPI, translates filings to English on demand, and classifies
            5%-rule filers against a named-entity list (foreign holders such as
            BlackRock, Vanguard, Norges, GIC, Temasek; Korean activists such as
            KCGI, Align Partners, ValueAct, Elliott). It is one honest option
            for option 3 above — here is how to connect it.
          </p>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            ChatGPT or Claude (hosted, no install)
          </h3>
          <p className="mt-3 text-zinc-300">
            Add the hosted endpoint as a custom connector:
          </p>
          <div className="mt-3 rounded bg-zinc-900 p-3 font-mono text-sm text-zinc-200 break-all">
            https://mcp.koreanpulse.dev/mcp
          </div>
          <ul className="mt-3 ml-5 list-disc space-y-1 text-sm text-zinc-300">
            <li>
              <strong className="text-zinc-100">ChatGPT</strong> — Settings →
              Connectors → Add custom connector → paste the URL. Authentication:
              None.
            </li>
            <li>
              <strong className="text-zinc-100">Claude</strong> — Settings →
              Connectors → Add custom connector → paste the URL.
            </li>
            <li>
              <strong className="text-zinc-100">OpenAI Responses API</strong> —
              add{" "}
              <code className="text-accent">
                {`{type: "mcp", server_url: "https://mcp.koreanpulse.dev/mcp"}`}
              </code>{" "}
              to your <code className="text-accent">tools</code> array.
            </li>
          </ul>
          <p className="mt-3 text-sm text-zinc-400">
            The free filing tools work without any DART key of your own — the
            hosted server uses a shared key for them.
          </p>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            Claude Desktop or Cursor (local install)
          </h3>
          <p className="mt-3 text-zinc-300">
            Install the package and add a small config block:
          </p>
          <pre className="mt-3 overflow-x-auto rounded bg-zinc-900 p-4 text-sm text-zinc-200">
{`pip install koreanpulse`}
          </pre>
          <pre className="mt-3 overflow-x-auto rounded bg-zinc-900 p-4 text-xs text-zinc-200">
{`{
  "mcpServers": {
    "koreanpulse": {
      "command": "koreanpulse",
      "env": {
        "DART_API_KEY": "your-free-dart-key",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}`}
          </pre>
          <p className="mt-3 text-sm text-zinc-400">
            The local path uses your own DART key (free, from
            opendart.fss.or.kr) and your own translation key. The full
            self-hosting guide is in the{" "}
            <a
              href="https://github.com/whdrnr2583-cmd/koreanpulse/blob/main/docs/SELF_HOSTING.md"
              className="text-accent hover:underline"
              rel="noopener noreferrer"
            >
              repository
            </a>
            .
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            The tools, and prompts that work
          </h2>
          <p className="mt-4 text-zinc-300">
            Once connected, the assistant has these filing-related tools
            available. You do not call them by name — you ask a normal
            question and the assistant picks the tool.
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <code className="text-accent">lookup_corp_code</code> — resolves a
              Korean company name (Hangul or romanized) to its DART corp code.
            </li>
            <li>
              <code className="text-accent">resolve_stock_code</code> — resolves
              a 6-digit KRX ticker (e.g. 005930) to a company.
            </li>
            <li>
              <code className="text-accent">track_korean_filings</code> — the
              core tool: recent DART filings for a company, translated to
              English.
            </li>
            <li>
              <code className="text-accent">monitor_foreign_holders</code> and{" "}
              <code className="text-accent">monitor_activist_investors</code> —
              5%-rule filings classified by who filed them.
            </li>
          </ul>
          <p className="mt-6 text-zinc-300">Prompts that work well:</p>
          <ul className="mt-2 space-y-2 text-zinc-300">
            <li>
              <em>
                &ldquo;Find Samsung Electronics in DART and show me its filings
                from the last 7 days, translated to English.&rdquo;
              </em>
            </li>
            <li>
              <em>
                &ldquo;What did the company with KRX ticker 000660 file
                recently?&rdquo;
              </em>{" "}
              (the assistant resolves 000660 → SK hynix first.)
            </li>
            <li>
              <em>
                &ldquo;Any 5%-rule shareholding disclosures on KOSPI names in
                the last two weeks?&rdquo;
              </em>
            </li>
          </ul>
          <p className="mt-4 text-zinc-300">
            A note on quotas: DART caps each API key at 40,000 calls/day. If
            you build your own server, cache filing-list responses with a
            short TTL so repeated questions about the same window do not burn
            quota. A hosted server handles this for you.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">A free way to start</h2>
          <p className="mt-4 text-zinc-300">
            Before connecting anything, you can see the shape of the data at{" "}
            <a href="/today" className="text-accent hover:underline">
              koreanpulse.dev/today
            </a>{" "}
            — a daily English snapshot of foreign-holder flows, activist
            filings, and major DART disclosures, refreshed at the Korean
            market close. No login, no key. There is a machine-readable
            version at{" "}
            <a href="/today.json" className="text-accent hover:underline">
              /today.json
            </a>{" "}
            if you want to parse it.
          </p>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/today"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              See today&apos;s DART snapshot →
            </a>
            <a
              href="/korean-stock-filings-in-english"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              Compare ways to read Korean filings in English
            </a>
          </div>

          <p className="mt-12 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
            <strong className="text-zinc-400">Not investment advice.</strong>{" "}
            koreanpulse translates and classifies primary-source public data
            (DART filings, Korean industry news). It is a data and intelligence
            service — it performs no individualized analysis and makes no
            recommendation to buy, sell, or hold any security. 자본시장법 §101
            면제 영역 — 일반 정보 데이터 제공.
          </p>
        </article>
      </div>
    </main>
  );
}
