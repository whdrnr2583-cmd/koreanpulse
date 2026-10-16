import type { Metadata } from "next";

const SITE = "https://koreanpulse.dev";
const PAGE_URL = `${SITE}/best-korean-stock-mcp-server`;
const DESC =
  "MCP servers that give an AI assistant access to Korean (KOSPI/KOSDAQ) stock " +
  "data, compared honestly: self-hosted OpenDART wrappers, korea-stock-mcp, " +
  "English-summary servers, and koreanpulse (hosted endpoint paused). Which to pick " +
  "for raw data, self-hosting, or English-first use.";

export const metadata: Metadata = {
  title: "The best MCP server for Korean stocks, compared | koreanpulse",
  description: DESC,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "The best MCP server for Korean stocks, compared",
    description: DESC,
    type: "article",
    url: PAGE_URL,
    siteName: "koreanpulse",
  },
};

const articleLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "The best MCP server for Korean stocks, compared",
  description: DESC,
  url: PAGE_URL,
  about: [
    "MCP server",
    "Korean stock market",
    "DART filings",
    "KOSPI",
    "KOSDAQ",
    "Model Context Protocol",
  ],
  publisher: { "@type": "Organization", name: "koreanpulse", url: SITE },
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "What is the best MCP server for Korean stock data?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "It depends on what you need. If you read Korean and want raw DART " +
          "data on your own machine, a self-hosted OpenDART wrapper such as " +
          "jjlabsio/korea-stock-mcp is a good free choice (bring your own DART " +
          "key). If you want English-translated filings and cross-investor " +
          "classification, koreanpulse provides them; install it yourself " +
          "(pip install koreanpulse, with your own DART key). Its hosted " +
          "endpoint (https://mcp.koreanpulse.dev/mcp) has been paused since " +
          "2026-09-21, so a one-URL connector setup is not available right now.",
      },
    },
    {
      "@type": "Question",
      name: "Do Korean stock MCP servers require a DART API key?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Most do. Self-hosted servers wrap the DART OpenAPI and require you " +
          "to register a free key at opendart.fss.or.kr (40,000 calls/day). " +
          "koreanpulse's hosted endpoint used a shared key for its free filing " +
          "tools, but that endpoint has been paused since 2026-09-21; " +
          "self-hosting koreanpulse uses your own key.",
      },
    },
    {
      "@type": "Question",
      name: "Can I connect a Korean stock MCP server to ChatGPT and Claude?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Yes, if the server exposes a remote HTTP endpoint (Streamable HTTP " +
          "or SSE). Add the URL as a custom connector. Many Korean-data MCP " +
          "servers are stdio-only, which works in Claude Desktop or Cursor but " +
          "not as a remote ChatGPT/Claude.ai connector. koreanpulse's hosted " +
          "remote endpoint (https://mcp.koreanpulse.dev/mcp) has been paused " +
          "since 2026-09-21; the server can be self-hosted over stdio.",
      },
    },
  ],
};

export default function BestKoreanStockMcpServer() {
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
          <span>Best Korean stock MCP server</span>
        </header>

        <article className="mt-10">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            The best MCP server for Korean stocks, compared
          </h1>

          <p className="mt-6 text-lg text-zinc-300">
            If you want an AI assistant — ChatGPT, Claude, or Cursor — to answer
            questions about Korean (KOSPI / KOSDAQ) companies using real filings
            rather than stale training data, you need a{" "}
            <strong className="text-zinc-100">Model Context Protocol (MCP)</strong>{" "}
            server that wraps a Korean data source. Several exist. This page
            compares the honest options by the choice that actually matters:
            how much friction you accept, and whether you need the data in
            English.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            The data source is the same; the wrapper is the difference
          </h2>
          <p className="mt-4 text-zinc-300">
            Almost every Korean stock MCP server is, underneath, a wrapper over{" "}
            <strong className="text-zinc-100">DART</strong> (전자공시시스템) — the
            Financial Supervisory Service&apos;s electronic disclosure system,
            the canonical free source for every KOSPI/KOSDAQ filing, and its{" "}
            <a
              href="https://opendart.fss.or.kr/"
              className="text-accent hover:underline"
              rel="noopener noreferrer"
            >
              OpenAPI
            </a>{" "}
            (free key, 40,000 calls/day). So the comparison is not about who has
            the data — it is the same public data — but about three things:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">Friction</strong> — do you have
              to register a DART key and install/run a process, or can you paste
              one URL? (koreanpulse&apos;s one-URL endpoint is paused since
              2026-09-21, so it currently needs a self-install.)
            </li>
            <li>
              <strong className="text-zinc-100">Language</strong> — does it
              return Korean filing titles and field values, or English?
            </li>
            <li>
              <strong className="text-zinc-100">Intelligence</strong> — raw
              filings only, or also cross-investor classification (who filed a
              5%-rule disclosure: a global asset manager? an activist?)?
            </li>
          </ul>

          <h2 className="mt-12 text-2xl font-semibold">The options</h2>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            1. Self-hosted OpenDART wrappers (e.g. korea-stock-mcp, OpenDART MCP)
          </h3>
          <p className="mt-3 text-zinc-300">
            Open-source MCP servers such as{" "}
            <code className="text-accent">jjlabsio/korea-stock-mcp</code> and
            various OpenDART-based servers wrap the DART OpenAPI and run locally
            over stdio. You register your own free DART key, install the server
            (npx or pip), and add it to your client config. They are free,
            transparent, and give you full control. The trade-offs: you maintain
            the key and quota yourself, most return filing data{" "}
            <strong className="text-zinc-100">in Korean</strong>, and stdio-only
            servers cannot be added as a remote connector in ChatGPT or
            Claude.ai (they work in Claude Desktop / Cursor).{" "}
            <strong className="text-zinc-100">Best if</strong> you read Korean,
            want raw data, and prefer everything on your own machine.
          </p>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            2. English-summary DART servers
          </h3>
          <p className="mt-3 text-zinc-300">
            A newer category (e.g.{" "}
            <code className="text-accent">koreafilings-mcp</code>) returns
            English-summarised DART filings, which removes the Korean-language
            barrier on raw filings. These are a real improvement for
            English-first readers over Korean-only wrappers.{" "}
            <strong className="text-zinc-100">Best if</strong> you want
            English-readable individual filings and are comfortable
            self-hosting / supplying your own key.
          </p>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            3. Translation + classification (koreanpulse; hosted endpoint paused)
          </h3>
          <p className="mt-3 text-zinc-300">
            <a href="/" className="text-accent hover:underline">
              koreanpulse
            </a>{" "}
            takes the same DART primary source and adds three things on top:
          </p>
          <ul className="mt-3 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">A hosted remote endpoint (paused)</strong>{" "}
              at{" "}
              <code className="text-accent">https://mcp.koreanpulse.dev/mcp</code>{" "}
              (Streamable HTTP + SSE). It has been paused since 2026-09-21 and
              does not accept connections, so for now run the server yourself
              with <code className="text-accent">pip install koreanpulse</code>{" "}
              and your own DART key.
            </li>
            <li>
              <strong className="text-zinc-100">English translation</strong> of
              filing titles and summaries on demand, cached so repeated queries
              are fast.
            </li>
            <li>
              <strong className="text-zinc-100">
                Cross-investor tagging
              </strong>{" "}
              — 5%-rule (대량보유보고) disclosures auto-tagged by who filed them:
              global passive holders (BlackRock, Vanguard, Norges Bank, GIC,
              Temasek and more) and Korean / global activists (KCGI, Align
              Partners, Truston, ValueAct, Elliott and more). A single firm&apos;s
              own English filing does not tell you this; it requires matching
              filers across the whole disclosure stream.
            </li>
          </ul>
          <p className="mt-3 text-zinc-300">
            The trade-off is honest: the hosted convenience tiers are paid
            (Cloud Solo $29/mo and up), and the cross-investor classification
            tools are part of those tiers. The whole server is AGPL open source,
            so you can self-host it with your own keys.{" "}
            <strong className="text-zinc-100">Best if</strong> you want
            English-first answers, or you specifically
            need to know <em>who</em> is crossing 5% in a name.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">Quick decision guide</h2>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">
                I read Korean and want raw, self-hosted data, free:
              </strong>{" "}
              a self-hosted OpenDART wrapper (option 1).
            </li>
            <li>
              <strong className="text-zinc-100">
                I want English filings but will self-host:
              </strong>{" "}
              an English-summary server (option 2), or self-host koreanpulse
              (AGPL).
            </li>
            <li>
              <strong className="text-zinc-100">
                I want English answers and I care who is buying:
              </strong>{" "}
              self-hosted koreanpulse (option 3; the hosted endpoint is paused
              since 2026-09-21).
            </li>
          </ul>

          <h2 className="mt-12 text-2xl font-semibold">Try it without committing</h2>
          <p className="mt-4 text-zinc-300">
            You can see exactly what the data looks like, with no install and no
            account, at{" "}
            <a href="/today" className="text-accent hover:underline">
              koreanpulse.dev/today
            </a>{" "}
            — a daily English snapshot of foreign-holder flows, activist filings,
            and major DART disclosures, with a machine-readable{" "}
            <a href="/today.json" className="text-accent hover:underline">
              /today.json
            </a>
            . The hosted MCP endpoint (
            <code className="text-accent">mcp.koreanpulse.dev/mcp</code>) is
            paused since 2026-09-21; to try the MCP itself, self-install it with{" "}
            <code className="text-accent">pip install koreanpulse</code>.
          </p>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/today"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              See the daily snapshot →
            </a>
            <a
              href="/track-korean-dart-filings-with-ai"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              How to wire it into your assistant
            </a>
          </div>

          <p className="mt-12 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
            <strong className="text-zinc-400">Not investment advice.</strong>{" "}
            koreanpulse translates and classifies primary-source public data
            (DART filings, Korean industry news). It is a data and intelligence
            service — it performs no individualized analysis and makes no
            recommendation to buy, sell, or hold any security. Comparisons
            describe setup and data-access trade-offs, not investment merit.
            일반 정보 데이터 제공 — 투자자문·투자권유에 해당하지 않습니다.
          </p>
        </article>
      </div>
    </main>
  );
}
