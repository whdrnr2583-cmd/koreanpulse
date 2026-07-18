import type { Metadata } from "next";

const SITE = "https://koreanpulse.dev";
const PAGE_URL = `${SITE}/monitor-korean-governance-foreign-holders`;
const DESC =
  "How to monitor Korean corporate governance disclosures — distress and " +
  "governance red-flag tags on every DART filing (audit opinion, delisting " +
  "risk, controlling-shareholder change, and more) — and how to track " +
  "foreign institutional 5%-rule holders in Korean (KOSPI/KOSDAQ) stocks, " +
  "in English.";

export const metadata: Metadata = {
  title:
    "How to monitor Korean corporate governance disclosures and foreign holders | koreanpulse",
  description: DESC,
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title:
      "How to monitor Korean corporate governance disclosures and foreign holders",
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
    "How to monitor Korean corporate governance disclosures and foreign holders",
  description: DESC,
  url: PAGE_URL,
  about: [
    "corporate governance Korea",
    "foreign institutional holder",
    "DART filings",
    "KOSPI",
    "KOSDAQ",
    "disclosure provenance",
  ],
  publisher: { "@type": "Organization", name: "koreanpulse", url: SITE },
};

const faqLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "What tools exist to monitor Korean corporate governance disclosures?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "DART itself carries every governance-relevant filing (audit " +
          "opinions, largest-shareholder changes, delisting events, capital " +
          "actions) but does not tag them — you have to read each Korean " +
          "title and know what it means. koreanpulse's track_korean_filings " +
          "tool (free tier) tags each filing with governance/distress " +
          "red-flag labels inferred from the title, in English, and can " +
          "filter a batch scan down to only the flagged ones.",
      },
    },
    {
      "@type": "Question",
      name: "What are Korean corporate governance red-flag filing types?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Common ones include a distress-only audit opinion (의견거절/한정/" +
          "부적정), administrative-issue designation (관리종목), delisting " +
          "risk (상장폐지), trading halt (거래정지), controlling-shareholder " +
          "change (최대주주변경), rights issue (유상증자), capital reduction " +
          "(감자), and going-concern doubt (계속기업/존속능력). A clean audit " +
          "opinion (적정) is not flagged.",
      },
    },
    {
      "@type": "Question",
      name: "How do I track foreign institutional ownership changes in Korean stocks?",
      acceptedAnswer: {
        "@type": "Answer",
        text:
          "Foreign institutional holders file the same 5%-rule disclosure " +
          "(대량보유보고) as everyone else when they cross 5% ownership or " +
          "shift a holding by 1% or more, but the filer name is in Korean " +
          "and DART does not label it 'foreign institutional holder'. " +
          "koreanpulse's monitor_foreign_holders tool tags each filing " +
          "against a maintained allowlist of named global asset managers " +
          "and sovereign wealth funds (BlackRock, Vanguard, Norges Bank, " +
          "GIC, Temasek, and more) — an allowlist tag, not a trained " +
          "classifier — and returns the result in English.",
      },
    },
  ],
};

export default function MonitorKoreanGovernanceForeignHolders() {
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
          <span>Monitor governance &amp; foreign holders</span>
        </header>

        <article className="mt-10">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
            How to monitor Korean corporate governance disclosures and
            foreign institutional holders
          </h1>

          <p className="mt-6 text-lg text-zinc-300">
            Two questions come up constantly for anyone tracking Korean
            (KOSPI/KOSDAQ) corporate filings in English: which of today&apos;s
            DART filings actually signal a governance or distress event, and
            which foreign institutional holders are moving positions. Both
            answers live inside the same DART disclosure stream — DART just
            does not label either one for you. This guide covers both.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Corporate governance disclosure monitoring
          </h2>
          <p className="mt-4 text-zinc-300">
            <strong className="text-zinc-100">DART</strong> (전자공시시스템),
            South Korea&apos;s corporate disclosure system, carries every
            governance-relevant filing — audit opinions, largest-shareholder
            changes, delisting events, capital actions — mixed in with routine
            periodic reports. Nothing in the raw feed marks a filing as
            governance-relevant; you have to read the Korean title and know
            what it means.
          </p>
          <p className="mt-4 text-zinc-300">
            koreanpulse&apos;s{" "}
            <code className="text-accent">track_korean_filings</code> tool
            (free tier, no license required) tags every corporate filing it
            returns with a <code className="text-accent">red_flags</code>{" "}
            list inferred from the title, and a{" "}
            <code className="text-accent">market</code> field (KOSPI /
            KOSDAQ / KONEX). The tags:
          </p>
          <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-1 text-sm text-zinc-300 sm:grid-cols-2">
            <li>
              <code className="text-accent">audit_opinion</code> — distress-only
              audit opinion (의견거절/한정/부적정)
            </li>
            <li>
              <code className="text-accent">going_concern</code> — going-concern
              doubt (계속기업/존속능력)
            </li>
            <li>
              <code className="text-accent">management_designation</code> —
              administrative-issue designation (관리종목)
            </li>
            <li>
              <code className="text-accent">delisting_risk</code> — delisting
              event/risk (상장폐지)
            </li>
            <li>
              <code className="text-accent">trading_halt</code> — trading
              suspension (거래정지)
            </li>
            <li>
              <code className="text-accent">controlling_shareholder_change</code>{" "}
              — largest-shareholder change (최대주주변경)
            </li>
            <li>
              <code className="text-accent">rehabilitation</code> — court
              receivership (회생절차)
            </li>
            <li>
              <code className="text-accent">disclosure_violation</code> —
              unfaithful-disclosure designation (불성실공시)
            </li>
            <li>
              <code className="text-accent">rights_issue</code> — paid-in
              capital increase (유상증자)
            </li>
            <li>
              <code className="text-accent">capital_reduction</code> — capital
              reduction (감자)
            </li>
            <li>
              <code className="text-accent">reverse_split</code> — share
              consolidation (주식병합)
            </li>
            <li>
              <code className="text-accent">short_term_borrowing</code> —
              short-term borrowing disclosure (단기차입금)
            </li>
          </ul>
          <p className="mt-4 text-zinc-300">
            A clean audit opinion (적정) is intentionally not tagged — only
            distress outcomes are. For portfolio-scale monitoring, the same
            tool accepts up to 10 corp codes and a{" "}
            <code className="text-accent">since</code> checkpoint in one
            batch call, with a{" "}
            <code className="text-accent">material_only</code> flag to return
            only the flagged filings — a way to scan a whole watchlist for
            governance events without re-reading every routine filing.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Foreign institutional holder tracking
          </h2>
          <p className="mt-4 text-zinc-300">
            Foreign institutional holders — global asset managers and
            sovereign wealth funds — cross the same{" "}
            <strong className="text-zinc-100">5%-rule disclosure</strong>{" "}
            (주식등의대량보유상황보고서, 대량보유보고) as any other filer when
            they cross 5% ownership of a listed Korean company, or shift an
            existing holding by 1% or more. DART records the filer name in
            Korean and does not classify it as &ldquo;foreign
            institutional.&rdquo; Even the FSS-operated{" "}
            <a
              href="https://englishdart.fss.or.kr/"
              className="text-accent hover:underline"
              rel="noopener noreferrer"
            >
              englishdart.fss.or.kr
            </a>{" "}
            — the official English DART portal — gives you one company&apos;s
            own filing in English, not a classified view across the whole
            5%-rule stream.
          </p>
          <p className="mt-4 text-zinc-300">
            koreanpulse&apos;s{" "}
            <code className="text-accent">monitor_foreign_holders</code> tool
            (part of the Cloud tier) tags each 5%-rule filing against a
            maintained allowlist of named foreign institutional holders —
            BlackRock, Vanguard, State Street, Fidelity, Norges Bank
            (Norway&apos;s sovereign fund), GIC and Temasek (Singapore), and
            more — and returns the disclosure in English. This is an
            allowlist tag, not a trained classifier: it matches the Korean
            filer name against a known-entity list rather than inferring
            anything from context.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">
            Monitoring both from an AI assistant
          </h2>
          <p className="mt-4 text-zinc-300">
            <a href="/" className="text-accent hover:underline">
              koreanpulse
            </a>{" "}
            is a hosted MCP server that wraps the DART primary source. Add the
            endpoint as a custom connector and ask a normal question — the
            assistant picks the tool and cites the underlying DART receipt
            number for every result:
          </p>
          <div className="mt-3 rounded bg-zinc-900 p-3 font-mono text-sm text-zinc-200 break-all">
            https://mcp.koreanpulse.dev/mcp
          </div>
          <p className="mt-4 text-zinc-300">Prompts that work:</p>
          <ul className="mt-2 space-y-2 text-zinc-300">
            <li>
              <em>
                &ldquo;Scan my Korean watchlist for any governance red flags
                since last Monday.&rdquo;
              </em>
            </li>
            <li>
              <em>
                &ldquo;Did any Korean company get a qualified or adverse audit
                opinion this month?&rdquo;
              </em>
            </li>
            <li>
              <em>
                &ldquo;Has BlackRock or Norges Bank crossed 5% on a KOSPI name
                recently?&rdquo;
              </em>
            </li>
          </ul>
          <p className="mt-4 text-sm text-zinc-400">
            The governance/distress red-flag tagging on{" "}
            <code className="text-accent">track_korean_filings</code> is part
            of the five free tools — no key, no license. Foreign-holder
            allowlist tagging is part of the Cloud tier (Solo $29/mo and up);
            the server is also AGPL open source if you prefer to self-host
            with your own DART key.
          </p>

          <h2 className="mt-12 text-2xl font-semibold">See it for free first</h2>
          <p className="mt-4 text-zinc-300">
            The public daily snapshot at{" "}
            <a href="/today" className="text-accent hover:underline">
              koreanpulse.dev/today
            </a>{" "}
            already shows the day&apos;s classified foreign-holder flows
            alongside major DART disclosures — no login, no key — so you can
            see the shape of the output before connecting anything.
          </p>

          <div className="mt-10 flex flex-wrap gap-3">
            <a
              href="/today"
              className="rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-ink hover:opacity-90"
            >
              See today&apos;s flows &amp; filings →
            </a>
            <a
              href="/track-foreign-investors-activists-korea"
              className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:border-zinc-500"
            >
              Track foreign investors &amp; activists
            </a>
          </div>

          <p className="mt-12 border-t border-zinc-800 pt-6 text-xs text-zinc-500">
            <strong className="text-zinc-400">Not investment advice.</strong>{" "}
            koreanpulse translates and tags primary-source public data (DART
            filings, Korean industry news). It is a data and intelligence
            service — it performs no individualized analysis and makes no
            recommendation to buy, sell, or hold any security. A red-flag tag
            or a foreign-holder allowlist match is not a view on the
            security. 자본시장법 §101 면제 영역 — 일반 정보 데이터 제공.
          </p>
        </article>
      </div>
    </main>
  );
}
