import type { Metadata } from "next";

const SITE = "https://koreanpulse.dev";
const PAGE_URL = `${SITE}/track-foreign-investors-activists-korea`;
const DESC =
  "How to track foreign institutional investors and activist campaigns in " +
  "Korean (KOSPI/KOSDAQ) stocks, in English. What the 5%-rule disclosure " +
  "(대량보유보고) is, who the major foreign holders and activists are, and how " +
  "to monitor their filings from an AI assistant.";

export const metadata: Metadata = {
  title:
    "How to track foreign investors and activists in Korean stocks (in English) | koreanpulse",
  description: DESC,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "How to track foreign investors and activists in Korean stocks",
    description: DESC,
    type: "article",
    url: PAGE_URL,
    siteName: "koreanpulse",
  },
};

const articleLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline:
    "How to track foreign investors and activists in Korean stocks (in English)",
  description: DESC,
  url: PAGE_URL,
  about: [
    "5%-rule disclosure",
    "foreign investors Korea",
    "activist investors Korea",
    "KOSPI",
    "KOSDAQ",
    "DART filings",
  ],
  publisher: { "@type": "Organization", name: "koreanpulse", url: SITE },
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "What is the 5%-rule disclosure in Korea?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "The 5%-rule disclosure (주식등의대량보유상황보고서, 대량보유보고) must be " +
          "filed in DART when an investor crosses 5% ownership of a listed " +
          "Korean company, and again whenever the holding shifts by 1% or more. " +
          "It is the leading public indicator of foreign capital entering a name " +
          "and of activist accumulation. It is filed in Korean.",
      },
    },
    {
      "@type": "Question",
      name: "How do I know if BlackRock or an activist filed on a Korean stock?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "The information is in the 5%-rule disclosure stream on DART, but the " +
          "filer name is in Korean and DART does not classify filers as " +
          "'foreign passive holder' or 'activist'. You either read the filings " +
          "in Korean and recognise the names, or use a service that matches " +
          "filer names against a known-entity list. koreanpulse's " +
          "monitor_foreign_holders and monitor_activist_investors tools do this " +
          "automatically and return the result in English.",
      },
    },
    {
      "@type": "Question",
      name: "Can I get Korean activist and foreign-holder filings in English?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Yes. koreanpulse translates the filings and tags each 5%-rule filer " +
          "against named global asset managers (BlackRock, Vanguard, Norges " +
          "Bank, GIC, Temasek and more) and activists (KCGI, Align Partners, " +
          "Truston, ValueAct, Elliott and more), delivered inside ChatGPT or " +
          "Claude via the hosted MCP endpoint https://mcp.koreanpulse.dev/mcp.",
      },
    },
  ],
};

export default function TrackForeignInvestorsActivistsKorea() {
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
          <span>Track foreign investors &amp; activists</span>
        </header>

        <article className="mt-10">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            How to track foreign investors and activists in Korean stocks
          </h1>

          <p className="mt-6 text-lg text-zinc-300">
            When a global asset manager builds a position in a KOSPI name, or an
            activist starts a campaign at a Korean company, the first public
            signal is almost always a <strong className="text-zinc-100">5%-rule
            disclosure</strong> filed in DART — in Korean. This guide explains
            what that filing is, who the players are, and how to monitor them in
            English from an AI assistant.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            The 5%-rule disclosure, and why it matters
          </h2>
          <p className="mt-4 text-zinc-300">
            Under Korean capital-markets law, anyone crossing{" "}
            <strong className="text-zinc-100">5% ownership</strong> of a listed
            company must file a large-holding report
            (주식등의대량보유상황보고서, commonly 대량보유보고) in DART, and must
            update it whenever the stake moves by{" "}
            <strong className="text-zinc-100">1% or more</strong>. The report
            states who is buying, how much, and — critically — the{" "}
            <em>purpose</em> of holding (simple investment vs. influence over
            management). That purpose field is what separates a passive index
            inflow from an activist campaign.
          </p>
          <p className="mt-4 text-zinc-300">
            It is the single most-watched DART filing type for anyone following
            capital flow, because it is a leading indicator: it shows
            accumulation as it happens, before it shows up in news or quarterly
            holdings data.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">Who files them</h2>
          <p className="mt-4 text-zinc-300">
            Two groups matter most to foreign readers, and they call for
            different reading:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">
                Global passive / institutional holders
              </strong>{" "}
              — BlackRock, Vanguard, State Street, Norges Bank (Norway&apos;s
              sovereign fund), GIC and Temasek (Singapore), and more. Their
              filings usually signal index or mandate-driven flow rather than a
              campaign, but the direction and size are still signal.
            </li>
            <li>
              <strong className="text-zinc-100">Activists</strong> — Korean
              activist funds (KCGI, Align Partners, Truston, Anda, Cha Partners,
              VIP) and global activists filing in Korea (ValueAct, Elliott).
              Their filings — especially with a management-influence purpose —
              often precede board pushes, dividend campaigns, or governance
              fights.
            </li>
          </ul>

          <h2 className="mt-12 text-2xl font-semibold">
            Why this is hard to do from outside Korea
          </h2>
          <p className="mt-4 text-zinc-300">
            The data is public and free on DART. The friction is twofold. First,
            everything — filer names, the purpose field, the security
            description — is in Korean. Second, and less obvious:{" "}
            <strong className="text-zinc-100">
              DART does not classify filers
            </strong>
            . It will not tell you &ldquo;this filer is a global passive
            holder&rdquo; or &ldquo;this one is an activist.&rdquo; You have to
            recognise the Korean rendering of the filer name and know its
            category yourself. Even the FSS-mandated English DART filings for
            large caps give you one company&apos;s own filing — not a classified
            view across the whole 5%-rule stream.
          </p>
          <p className="mt-4 text-zinc-300">
            That cross-filer classification — matching every 5%-rule filer
            against a known-entity list and tagging it foreign-passive vs.
            activist — is the work that otherwise takes a Korean-reading analyst
            doing it by hand.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Monitoring it from an AI assistant
          </h2>
          <p className="mt-4 text-zinc-300">
            <a href="/" className="text-accent hover:underline">
              koreanpulse
            </a>{" "}
            is an MCP server that does exactly this classification and returns it
            in English. Connected to ChatGPT or Claude, it exposes two tools for
            this use case:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <code className="text-accent">monitor_foreign_holders</code> —
              recent 5%-rule disclosures auto-tagged for global passive /
              institutional holders (BlackRock, Vanguard, State Street, Norges,
              GIC, Temasek + more).
            </li>
            <li>
              <code className="text-accent">monitor_activist_investors</code> —
              recent 5%-rule disclosures auto-tagged for known activists (KCGI,
              Align, Truston, Anda, Cha, VIP, ValueAct, Elliott).
            </li>
          </ul>
          <p className="mt-4 text-zinc-300">
            You do not call tools by name — you ask a normal question and the
            assistant picks the tool. Prompts that work:
          </p>
          <ul className="mt-2 space-y-2 text-zinc-300">
            <li>
              <em>
                &ldquo;Any activist 5%-rule filings on Korean companies in the
                last two weeks?&rdquo;
              </em>
            </li>
            <li>
              <em>
                &ldquo;Did any global asset manager cross 5% on a KOSPI name
                recently? Translate the filings.&rdquo;
              </em>
            </li>
            <li>
              <em>
                &ldquo;Show me Elliott or ValueAct activity in Korea this
                month.&rdquo;
              </em>
            </li>
          </ul>

          <h3 className="mt-8 text-lg font-semibold text-zinc-100">
            Connecting it
          </h3>
          <p className="mt-3 text-zinc-300">
            Add the hosted endpoint as a custom connector in ChatGPT (Settings →
            Connectors) or Claude:
          </p>
          <div className="mt-3 rounded bg-zinc-900 p-3 font-mono text-sm text-zinc-200 break-all">
            https://mcp.koreanpulse.dev/mcp
          </div>
          <p className="mt-3 text-sm text-zinc-400">
            The five free tools (including live filing retrieval and
            translation) need no key. The two classification tools above are
            part of the Cloud tier (Solo $29/mo and up); the server is also AGPL
            open source if you prefer to self-host with your own keys.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">See it for free first</h2>
          <p className="mt-4 text-zinc-300">
            The public daily snapshot at{" "}
            <a href="/today" className="text-accent hover:underline">
              koreanpulse.dev/today
            </a>{" "}
            already shows the classified foreign-holder flows and activist
            filings for the latest Korean market close — no login, no key — so
            you can see the shape of the output before connecting anything.
          </p>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/today"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              See today&apos;s flows &amp; filings →
            </a>
            <a
              href="/best-korean-stock-mcp-server"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              Compare Korean stock MCP servers
            </a>
          </div>

          <p className="mt-12 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
            <strong className="text-zinc-400">Not investment advice.</strong>{" "}
            koreanpulse translates and classifies primary-source public data
            (DART filings, Korean industry news). It is a data and intelligence
            service — it performs no individualized analysis and makes no
            recommendation to buy, sell, or hold any security. Identifying that
            an investor filed a disclosure is not a view on the security.
            자본시장법 §101 면제 영역 — 일반 정보 데이터 제공.
          </p>
        </article>
      </div>
    </main>
  );
}
