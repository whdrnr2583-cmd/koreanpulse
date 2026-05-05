/**
 * HTML rendering for /today.
 *
 * Self-contained — Tailwind via CDN, no build step. Page weight < 30 KB.
 * Render is pure: takes a daily snapshot and returns HTML string.
 *
 * Brand colors match docs/assets/logo.svg: bg #0E1116, accent #F0B429.
 */

import type { ActivistFiling, DartFiling, ForeignFlowFiling } from "./dart";
import type { InvestorMatch } from "./activists";

/**
 * Stable schema returned by /today.json. Versioned so AI clients can
 * pin against a known shape; bump on breaking change.
 *
 * v2 (2026-05-05): added `takeaway` array — 1–3 LLM-generated English
 * bullets summarising the day's most material moves. Backwards-compatible
 * additive field, but bumped for clarity.
 */
export const SNAPSHOT_SCHEMA_VERSION = 2;

export interface DailySnapshot {
  schema_version: number;
  date: string;                // ISO yyyy-mm-dd (KST)
  generated_at: string;        // ISO datetime UTC
  market: "KRX";
  takeaway: string[];          // 1–3 short English bullets, may be empty
  activist_filings: ActivistFilingEnriched[];
  foreign_flows: ForeignFlowEnriched[];
  top_filings: FilingEnriched[];
  attribution: string;
  data_sources: { name: string; url: string }[];
  legal_notice: string;
}

export interface FilingEnriched extends DartFiling {
  title_en: string;
  summary_en?: string;
}

export interface ActivistFilingEnriched extends ActivistFiling {
  title_en: string;
  summary_en?: string;
}

export interface ForeignFlowEnriched extends ForeignFlowFiling {
  title_en: string;
  summary_en?: string;
}

const ORIGIN_FLAG: Record<InvestorMatch["origin"], string> = {
  us: "🇺🇸",
  uk: "🇬🇧",
  eu: "🇪🇺",
  other: "🌐",
  kr: "🇰🇷",
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function foreignFlowRow(f: ForeignFlowEnriched): string {
  const ticker = f.stock_code ? `<span class="text-xs text-stone-400 ml-2">${escapeHtml(f.stock_code)}</span>` : "";
  const flag = ORIGIN_FLAG[f.holder_origin] ?? "🌐";
  return `
    <article class="border border-stone-800 rounded-lg p-4 hover:border-emerald-500/50 transition">
      <div class="flex items-baseline justify-between gap-3 mb-2">
        <span class="inline-block px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-300 rounded">${flag} ${escapeHtml(f.holder_label)}</span>
        <time class="text-xs text-stone-500">${escapeHtml(f.filed_at)}</time>
      </div>
      <h3 class="text-base font-medium text-stone-100 mb-1">
        <a href="${escapeHtml(f.dart_url)}" rel="noopener noreferrer" target="_blank" class="hover:text-emerald-400">
          ${escapeHtml(f.title_en || f.title)}
        </a>
      </h3>
      <div class="text-sm text-stone-400 mb-2">
        Disclosed by <span class="text-stone-300">${escapeHtml(f.filer_name_ko ?? "—")}</span>
        on <span class="text-stone-300">${escapeHtml(f.corp_name_en || f.corp_name_ko)}</span>${f.corp_name_en && f.corp_name_en !== f.corp_name_ko ? ` <span class="text-xs text-stone-500">${escapeHtml(f.corp_name_ko)}</span>` : ""}${ticker}
      </div>
      ${f.summary_en ? `<p class="text-sm text-stone-300 leading-relaxed">${escapeHtml(f.summary_en)}</p>` : ""}
      <div class="text-xs text-stone-500 mt-2">
        <span class="font-mono">${escapeHtml(f.title)}</span>
      </div>
    </article>`;
}

function activistRow(f: ActivistFilingEnriched): string {
  const ticker = f.stock_code ? `<span class="text-xs text-stone-400 ml-2">${escapeHtml(f.stock_code)}</span>` : "";
  return `
    <article class="border border-stone-800 rounded-lg p-4 hover:border-amber-500/50 transition">
      <div class="flex items-baseline justify-between gap-3 mb-2">
        <span class="inline-block px-2 py-0.5 text-xs font-semibold bg-amber-500/20 text-amber-300 rounded">${escapeHtml(f.activist_label)}</span>
        <time class="text-xs text-stone-500">${escapeHtml(f.filed_at)}</time>
      </div>
      <h3 class="text-base font-medium text-stone-100 mb-1">
        <a href="${escapeHtml(f.dart_url)}" rel="noopener noreferrer" target="_blank" class="hover:text-amber-400">
          ${escapeHtml(f.title_en || f.title)}
        </a>
      </h3>
      <div class="text-sm text-stone-400 mb-2">
        Filed by <span class="text-stone-300">${escapeHtml(f.filer_name_ko ?? "—")}</span>
        on <span class="text-stone-300">${escapeHtml(f.corp_name_en || f.corp_name_ko)}</span>${f.corp_name_en && f.corp_name_en !== f.corp_name_ko ? ` <span class="text-xs text-stone-500">${escapeHtml(f.corp_name_ko)}</span>` : ""}${ticker}
      </div>
      ${f.summary_en ? `<p class="text-sm text-stone-300 leading-relaxed">${escapeHtml(f.summary_en)}</p>` : ""}
      <div class="text-xs text-stone-500 mt-2">
        <span class="font-mono">${escapeHtml(f.title)}</span>
      </div>
    </article>`;
}

function filingRow(f: FilingEnriched): string {
  const ticker = f.stock_code ? `<span class="text-xs text-stone-400 ml-2">${escapeHtml(f.stock_code)}</span>` : "";
  return `
    <li class="border-l-2 border-stone-700 pl-4 hover:border-amber-500 transition">
      <div class="flex items-baseline justify-between gap-3">
        <h3 class="text-sm font-medium text-stone-100">
          <a href="${escapeHtml(f.dart_url)}" rel="noopener noreferrer" target="_blank" class="hover:text-amber-400">
            ${escapeHtml(f.title_en || f.title)}
          </a>
        </h3>
        <time class="text-xs text-stone-500 shrink-0">${escapeHtml(f.filed_at)}</time>
      </div>
      <div class="text-xs text-stone-400 mt-1">
        ${escapeHtml(f.corp_name_en || f.corp_name_ko)}${f.corp_name_en && f.corp_name_en !== f.corp_name_ko ? ` <span class="text-stone-500">${escapeHtml(f.corp_name_ko)}</span>` : ""}${ticker}
      </div>
    </li>`;
}

export function renderDaily(snap: DailySnapshot): string {
  const title = `koreanpulse / today — ${snap.date}`;
  const description = `Korean equity disclosures, activist filings, and industry news — ${snap.date}, summarised in English.`;
  const ogUrl = `https://koreanpulse.dev/today`;

  const activistSection = snap.activist_filings.length
    ? snap.activist_filings.map(activistRow).join("\n")
    : `<p class="text-stone-500 text-sm">No activist filings in the last 7 days.</p>`;

  const foreignSection = snap.foreign_flows.length
    ? snap.foreign_flows.map(foreignFlowRow).join("\n")
    : `<p class="text-stone-500 text-sm">No foreign-holder 5%-rule filings in the last 7 days.</p>`;

  const topSection = snap.top_filings.length
    ? `<ul class="space-y-3">${snap.top_filings.map(filingRow).join("\n")}</ul>`
    : `<p class="text-stone-500 text-sm">No major filings today.</p>`;

  const takeawaySection = snap.takeaway.length
    ? `<ul class="space-y-2 text-zinc-200">${snap.takeaway
        .map(
          (b) =>
            `<li class="flex gap-2"><span class="text-amber-400 shrink-0">›</span><span>${escapeHtml(
              b,
            )}</span></li>`,
        )
        .join("\n")}</ul>`
    : `<p class="text-stone-500 text-sm">No takeaway today — quiet day on KRX.</p>`;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(description)}">
  <meta property="og:title" content="${escapeHtml(title)}">
  <meta property="og:description" content="${escapeHtml(description)}">
  <meta property="og:url" content="${escapeHtml(ogUrl)}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="${escapeHtml(ogUrl)}">
  <link rel="alternate" type="application/json" href="/today.json">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background: #0E1116; }
  </style>
</head>
<body class="text-stone-200 min-h-screen">
  <div class="max-w-3xl mx-auto px-4 py-10">
    <header class="mb-10 border-b border-stone-800 pb-6">
      <div class="flex items-baseline justify-between">
        <a href="/" class="text-amber-400 text-2xl font-semibold tracking-tight">koreanpulse</a>
        <nav class="flex gap-4 text-sm text-stone-400">
          <a href="/today" class="text-stone-100">today</a>
          <a href="/pricing" class="hover:text-stone-100">pricing</a>
          <a href="https://github.com/whdrnr2583-cmd/koreanpulse" rel="noopener noreferrer" target="_blank" class="hover:text-stone-100">github</a>
        </nav>
      </div>
      <h1 class="text-3xl font-bold text-stone-100 mt-6">Today on KOSPI / KOSDAQ</h1>
      <p class="text-stone-400 mt-2 text-sm">${escapeHtml(snap.date)} · DART activist filings + key disclosures · English summaries</p>
    </header>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-3 flex items-center gap-2">
        <span>Today's takeaway</span>
        <span class="text-xs font-normal text-stone-500">AI-summarised</span>
      </h2>
      <div class="rounded-md border border-amber-500/20 bg-amber-500/5 p-4">
        ${takeawaySection}
      </div>
    </section>

    <section class="mb-10 rounded-md border border-emerald-800/40 bg-emerald-500/5 p-4">
      <div class="flex items-baseline gap-2 mb-2">
        <span class="rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-300">2026 inflection</span>
        <span class="text-xs text-stone-400">why this dashboard exists right now</span>
      </div>
      <p class="text-sm text-stone-300 leading-relaxed">
        Foreign retail just got direct access to KRX in the last 7 days:
        <strong class="text-stone-100">Hana × Futu</strong> (3.3M HK retail) launched late April 2026,
        <strong class="text-stone-100">Samsung × Interactive Brokers</strong> (4.6M global retail) pilot launched May 4 — same day foreigners net-bought a record
        <strong class="text-stone-100">3.9 trillion KRW (~$2.7B)</strong> on KOSPI+NXT.
        ~7.9M foreign retail accounts now wired in, up from ~0 two years ago.
        The English-data layer for this audience is what koreanpulse ships.
        <a href="https://github.com/whdrnr2583-cmd/koreanpulse/blob/main/_workspace/foreign_retail_inflow_2026-05-05.md" rel="noopener noreferrer" target="_blank" class="text-emerald-400 hover:underline">Sources →</a>
      </p>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-1 flex items-center gap-2">
        <span>Foreign capital activity</span>
        <span class="text-xs font-normal text-stone-500">${snap.foreign_flows.length} matched</span>
      </h2>
      <p class="text-xs text-stone-500 mb-4">5%-rule disclosures by global asset managers / sovereign wealth funds. Leading indicator of foreign money entering or exiting a Korean ticker.</p>
      <div class="space-y-3">${foreignSection}</div>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-1 flex items-center gap-2">
        <span>Activist filings</span>
        <span class="text-xs font-normal text-stone-500">${snap.activist_filings.length} matched</span>
      </h2>
      <p class="text-xs text-stone-500 mb-4">Type-D shareholding disclosures filed by funds known for governance pressure (KCGI, Align Partners, Truston, ValueAct, Elliott, etc.).</p>
      <div class="space-y-3">${activistSection}</div>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-4 flex items-center gap-2">
        <span>Major filings (last 24h)</span>
        <span class="text-xs font-normal text-stone-500">${snap.top_filings.length} latest</span>
      </h2>
      ${topSection}
    </section>

    <footer class="border-t border-stone-800 pt-6 mt-12 text-xs text-stone-500 space-y-2">
      <p>Generated ${escapeHtml(snap.generated_at)} · ${escapeHtml(snap.attribution)}</p>
      <p>Want this every weekday in your inbox / Discord? <a href="/pricing" class="text-amber-400 hover:underline">Subscribe</a> · <a href="/today.json" class="text-amber-400 hover:underline">JSON</a> · <a href="https://github.com/whdrnr2583-cmd/koreanpulse" rel="noopener noreferrer" target="_blank" class="hover:underline">Source (AGPL-3.0)</a></p>
      <p class="text-stone-600">No investment advice — data + summary only. Korean broker reports excluded. Fair-use attribution per source.</p>
    </footer>
  </div>
</body>
</html>`;
}
