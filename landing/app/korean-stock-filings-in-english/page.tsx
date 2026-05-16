import type { Metadata } from "next";

const SITE = "https://koreanpulse.dev";
const PAGE_URL = `${SITE}/korean-stock-filings-in-english`;
const DESC =
  "The South Korean disclosure system DART (전자공시) is the canonical source for " +
  "KOSPI/KOSDAQ filings, but it is Korean-only. Four ways to access Korean stock " +
  "filings in English, compared.";

export const metadata: Metadata = {
  title: "How to get Korean stock filings (DART) in English | koreanpulse",
  description: DESC,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "How to get Korean stock filings (DART) in English",
    description: DESC,
    type: "article",
    url: PAGE_URL,
    siteName: "koreanpulse",
  },
};

const articleLd = {
  "@context": "https://schema.org",
  "@type": "TechArticle",
  headline: "How to get Korean stock filings (DART) in English",
  description: DESC,
  url: PAGE_URL,
  about: ["Korean equities", "DART filings", "KOSPI", "KOSDAQ", "Korean stock disclosures"],
  publisher: { "@type": "Organization", name: "koreanpulse", url: SITE },
};

export default function KoreanFilingsGuide() {
  return (
    <main className="min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }}
      />
      <div className="mx-auto max-w-3xl">
        <header className="flex items-center gap-2 text-sm text-zinc-400">
          <a href="/" className="font-semibold text-zinc-200 hover:text-zinc-100">
            koreanpulse
          </a>
          <span>/</span>
          <span>Korean stock filings in English</span>
        </header>

        <article className="mt-10">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            How to get Korean stock filings (DART) in English
          </h1>

          <p className="mt-6 text-lg text-zinc-300">
            The South Korean corporate disclosure system —{" "}
            <strong className="text-zinc-100">DART</strong> (전자공시시스템), run by the
            Financial Supervisory Service — is the canonical, real-time source for every
            KOSPI, KOSDAQ, and KONEX filing: 5%-rule shareholding disclosures, activist
            filings, M&amp;A, capital raises, and periodic reports. It is free and public.
            It is also <strong className="text-zinc-100">Korean-only</strong>.
          </p>
          <p className="mt-4 text-zinc-300">
            English coverage of Korean disclosures is, by the on-record admission of KRX
            itself, ASIFMA, Wellington, Aberdeen, and Matthews Asia, structurally inadequate
            — often hours late, frequently absent. An investor who researches Korean
            equities without reading Korean works from a degraded copy of the primary
            source.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">What filings actually matter</h2>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">5%-rule disclosures</strong> (대량보유보고) —
              filed when an investor crosses 5% ownership or shifts holdings by 1% or more.
              The leading indicator of foreign capital flow and activist accumulation.
            </li>
            <li>
              <strong className="text-zinc-100">Activist filings</strong> — Korean activists
              (KCGI, Align Partners, Truston, Anda, Cha Partners, VIP) and global activists
              filing in Korea (ValueAct, Elliott).
            </li>
            <li>
              <strong className="text-zinc-100">Major business events</strong> (주요사항보고)
              — capital raises, M&amp;A, spinoffs, convertible-bond issuance.
            </li>
            <li>
              <strong className="text-zinc-100">Industry news</strong> — 전자신문 (etnews)
              and 한국경제 carry sector-level signal that rarely reaches English wires.
            </li>
          </ul>

          <h2 className="mt-12 text-2xl font-semibold">Four ways to access it</h2>
          <ol className="mt-4 space-y-3 text-zinc-300">
            <li>
              <strong className="text-zinc-100">1. Read DART directly.</strong> Free,
              canonical, real-time at dart.fss.or.kr — but it requires reading Korean.
            </li>
            <li>
              <strong className="text-zinc-100">2. Bloomberg / FactSet.</strong> English,
              but roughly $24K per year, and thin on Korean primary-source depth.
            </li>
            <li>
              <strong className="text-zinc-100">3. English wire services</strong> (KED
              Global, Korea Bizwire). Cheap, but reactive and low-signal — they report what
              is already news.
            </li>
            <li>
              <strong className="text-zinc-100">4. koreanpulse.</strong> Translates and
              classifies the same DART primary source into English, on demand, priced for
              individuals and small teams.
            </li>
          </ol>

          <h2 className="mt-12 text-2xl font-semibold">How koreanpulse does it</h2>
          <p className="mt-4 text-zinc-300">
            koreanpulse is an <strong className="text-zinc-100">MCP server</strong>. It
            exposes the DART primary source as typed tools that an AI client — ChatGPT,
            Claude.ai, Cursor, or Claude Desktop — can call directly:
          </p>
          <ul className="mt-4 space-y-2 text-zinc-300">
            <li>
              <code className="text-accent">track_korean_filings</code> — recent DART
              filings, translated to English.
            </li>
            <li>
              <code className="text-accent">monitor_foreign_holders</code> and{" "}
              <code className="text-accent">monitor_activist_investors</code> — 5%-rule
              disclosures auto-classified against a named-entity allowlist (BlackRock,
              Vanguard, Norges, GIC, Temasek and more; KCGI, Align, ValueAct, Elliott and
              more).
            </li>
            <li>
              <code className="text-accent">search_korean_industry_news</code> — etnews and
              한국경제 across 16 sectors — plus{" "}
              <code className="text-accent">lookup_corp_code</code>,{" "}
              <code className="text-accent">resolve_stock_code</code>, and{" "}
              <code className="text-accent">koreanpulse_about</code>.
            </li>
          </ul>
          <p className="mt-6 text-zinc-300">Two free ways to start:</p>
          <ul className="mt-2 space-y-2 text-zinc-300">
            <li>
              <strong className="text-zinc-100">Public daily snapshot.</strong> A daily
              English digest of foreign-holder flows, activist filings, and major DART
              disclosures at{" "}
              <a href="/today" className="text-accent hover:underline">
                koreanpulse.dev/today
              </a>{" "}
              — no login, no key.
            </li>
            <li>
              <strong className="text-zinc-100">Connect the MCP.</strong> Add{" "}
              <code className="text-accent">https://mcp.koreanpulse.dev/mcp</code> as a
              custom connector in ChatGPT or Claude.ai, then ask it for new DART filings on
              a ticker and get an English answer in the chat.
            </li>
          </ul>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/today"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              Preview the daily digest →
            </a>
            <a
              href="/#pricing"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              See pricing
            </a>
          </div>

          <p className="mt-12 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
            <strong className="text-zinc-400">Not investment advice.</strong> koreanpulse
            translates and classifies primary-source public data (DART filings, Korean
            industry news). It is not investment advice and performs no individualized
            analysis or recommendation. 자본시장법 §101 면제 영역 — 일반 정보 데이터 제공.
          </p>
        </article>
      </div>
    </main>
  );
}
