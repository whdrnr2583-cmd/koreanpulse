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
export const SNAPSHOT_SCHEMA_VERSION = 3;

export interface DailySnapshot {
  schema_version: number;
  date: string;                // ISO yyyy-mm-dd (KST)
  generated_at: string;        // ISO datetime UTC
  market: "KRX";
  takeaway: string[];          // 1–3 short English bullets, may be empty
  activist_filings: ActivistFilingEnriched[];
  foreign_flows: ForeignFlowEnriched[];
  top_filings: FilingEnriched[];
  // Present only when a DART stream failed and its section is blank for that
  // reason rather than because KRX was quiet. Absent on a clean build — the
  // two cases are otherwise identical in every field below, which is exactly
  // the confusion this exists to prevent. Human-readable stream names.
  degraded?: string[];
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

  // A blank section can mean "nothing was filed" or "we couldn't reach DART".
  // Only the snapshot knows which, so the copy below has to ask it — saying
  // "No activist filings" during an outage is a false statement about KRX.
  const failed = (stream: string) => (snap.degraded ?? []).includes(stream);
  const unavailable = (what: string) =>
    `<p class="text-amber-400/90 text-sm">Couldn't fetch ${what} from DART for this build — this section is incomplete, not empty.</p>`;

  const degradedBanner = snap.degraded?.length
    ? `<div class="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
         <strong class="font-semibold">Partial build.</strong> DART did not return ${escapeHtml(
           snap.degraded.join(" and "),
         )} for ${escapeHtml(snap.date)}. Those sections below are missing data, not reporting an absence of activity.
       </div>`
    : "";

  const activistSection = snap.activist_filings.length
    ? snap.activist_filings.map(activistRow).join("\n")
    : failed("activist and foreign-holder filings")
      ? unavailable("activist filings")
      : `<p class="text-stone-500 text-sm">No activist filings in the 7 days ending ${escapeHtml(snap.date)}.</p>`;

  const foreignSection = snap.foreign_flows.length
    ? snap.foreign_flows.map(foreignFlowRow).join("\n")
    : failed("activist and foreign-holder filings")
      ? unavailable("foreign-holder filings")
      : `<p class="text-stone-500 text-sm">No foreign-holder 5%-rule filings in the 7 days ending ${escapeHtml(snap.date)}.</p>`;

  const topSection = snap.top_filings.length
    ? `<ul class="space-y-3">${snap.top_filings.map(filingRow).join("\n")}</ul>`
    : failed("major filings")
      ? unavailable("major filings")
      : `<p class="text-stone-500 text-sm">No major filings on ${escapeHtml(snap.date)}.</p>`;

  const takeawaySection = snap.takeaway.length
    ? `<ul class="space-y-2 text-zinc-200">${snap.takeaway
        .map(
          (b) =>
            `<li class="flex gap-2"><span class="text-amber-400 shrink-0">›</span><span>${escapeHtml(
              b,
            )}</span></li>`,
        )
        .join("\n")}</ul>`
    : snap.degraded?.length
      ? `<p class="text-amber-400/90 text-sm">No takeaway — the build ran on incomplete DART data.</p>`
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

    ${degradedBanner}

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-3 flex items-center gap-2">
        <span>Today's takeaway</span>
        <span class="text-xs font-normal text-stone-500">AI-summarised</span>
      </h2>
      <div class="rounded-md border border-amber-500/20 bg-amber-500/5 p-4">
        ${takeawaySection}
      </div>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-1 flex items-center gap-2">
        <span>Foreign capital activity</span>
        <span class="text-xs font-normal text-stone-500">${snap.foreign_flows.length} matched</span>
      </h2>
      <p class="text-xs text-stone-500 mb-4">5%-rule disclosures whose filer matched a maintained list of global asset managers and sovereign wealth funds. Each item links to the original DART filing.</p>
      <div class="space-y-3">${foreignSection}</div>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-1 flex items-center gap-2">
        <span>Activist filings</span>
        <span class="text-xs font-normal text-stone-500">${snap.activist_filings.length} matched</span>
      </h2>
      <p class="text-xs text-stone-500 mb-4">Type-D shareholding disclosures whose filer matched a maintained list of funds known for governance campaigns (KCGI, Align Partners, Truston, ValueAct, Elliott, etc.).</p>
      <div class="space-y-3">${activistSection}</div>
    </section>

    <section class="mb-10">
      <h2 class="text-xl font-semibold text-stone-100 mb-4 flex items-center gap-2">
        <span>Major filings — ${escapeHtml(snap.date)}</span>
        <span class="text-xs font-normal text-stone-500">${snap.top_filings.length} latest</span>
      </h2>
      ${topSection}
    </section>

    <footer class="border-t border-stone-800 pt-6 mt-12 text-xs text-stone-500 space-y-2">
      <p>Generated ${escapeHtml(snap.generated_at)} · ${escapeHtml(snap.attribution)}</p>
      <p>Snapshot data date: ${escapeHtml(snap.date)} · rebuilt each weekday after KOSPI close (16:30 KST) · <a href="/today.json" class="text-amber-400 hover:underline">JSON</a> · <a href="/pricing" class="text-amber-400 hover:underline">Pricing</a> · <a href="https://github.com/whdrnr2583-cmd/koreanpulse" rel="noopener noreferrer" target="_blank" class="hover:underline">Source (AGPL-3.0)</a></p>
      <p class="text-stone-600">Not investment advice — disclosure data and summaries only. Each item links to the original DART filing.</p>
    </footer>
  </div>
</body>
</html>`;
}
