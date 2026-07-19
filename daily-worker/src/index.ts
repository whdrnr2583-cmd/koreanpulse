/**
 * koreanpulse-daily entry point.
 *
 * Two surfaces:
 *   - scheduled() — runs on the cron trigger (KST 16:30 weekdays).
 *     Fetches DART, summarises, writes HTML + JSON to KV, pushes Discord.
 *   - fetch()      — serves /today, /today.json, /today/:date.
 *
 * KV layout:
 *   daily:html:latest                 ← most recent HTML render (string)
 *   daily:json:latest                 ← most recent JSON snapshot (string)
 *   daily:html:YYYY-MM-DD             ← per-date HTML (30-day TTL)
 *   daily:json:YYYY-MM-DD             ← per-date JSON  (30-day TTL)
 *   translate:t:<model>:<sha>          ← cached title translation
 *   translate:s:<model>:<sha>          ← cached short summary
 */

import { fetchClassifiedFilings, fetchTopFilings, type DartFiling } from "./dart";
import {
  generateTakeaway,
  summariseFiling,
  translateCorpName,
  translateTitle,
} from "./translate";
import {
  renderDaily,
  SNAPSHOT_SCHEMA_VERSION,
  type DailySnapshot,
  type FilingEnriched,
  type ActivistFilingEnriched,
  type ForeignFlowEnriched,
} from "./render";
import { postToDiscord } from "./discord";
import { computeFreshness, type Freshness } from "./freshness";

export interface Env {
  DAILY: KVNamespace;
  DART_API_KEY: string;
  DART_API_BASE: string;
  OPENAI_API_KEY: string;
  LLM_MODEL: string;
  SITE_URL: string;
  HISTORY_DAYS: string;
  DISCORD_WEBHOOK_URL?: string;
  KOREANPULSE_ADMIN_SECRET?: string;
}

const KV_HTML_LATEST = "daily:html:latest";
const KV_JSON_LATEST = "daily:json:latest";
const ATTRIBUTION = "Source: 금융감독원 전자공시시스템 DART (https://dart.fss.or.kr/)";

export default {
  async scheduled(
    event: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    // Observability: scheduled() previously logged nothing, so a failed
    // cron build vanished silently. (The 2026-05-08/05-15 Friday misses that
    // motivated this turned out to be no-fires — the "1-5" day-of-week field
    // meant Sun–Thu under Cloudflare's 1=Sunday numbering, see wrangler.toml —
    // but the logging stays: it is what distinguishes "cron did not run" from
    // "cron ran and failed".) Log the invocation + wrap buildDaily so a throw
    // is captured via console.error instead of disappearing inside waitUntil.
    console.log(
      `[cron] fired cron="${event.cron}" ` +
        `scheduledTime=${new Date(event.scheduledTime).toISOString()}`,
    );
    ctx.waitUntil(
      buildDaily(env)
        .then((result) => {
          console.log(`[cron] buildDaily ok ${JSON.stringify(result)}`);
        })
        .catch((exc) => {
          const message = exc instanceof Error ? exc.message : String(exc);
          console.error(
            `[cron] buildDaily FAILED: ${message}`,
            exc instanceof Error ? exc.stack : "",
          );
        }),
    );
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      // Freshness-aware health: lets an external monitor distinguish
      // "worker up, snapshot current" from "worker up, cron silently dead"
      // without parsing the full snapshot.
      const freshness = await latestFreshness(env);
      return json({
        status: "ok",
        snapshot: {
          state: freshness.state,
          snapshot_date: freshness.snapshot_date,
          generated_at: freshness.generated_at,
          expected_date: freshness.expected_date,
        },
      });
    }

    // Manual rebuild trigger for ops / first-time setup. POST + dedicated
    // KOREANPULSE_ADMIN_SECRET so DART_API_KEY (used to call the upstream
    // regulator API) doesn't double as a write-side auth secret. Branch
    // before the GET-only guard so POST reaches us here.
    if (url.pathname === "/admin/rebuild") {
      if (request.method !== "POST") {
        return json({ error: "method not allowed; use POST" }, 405);
      }
      const provided = request.headers.get("x-admin-key") ?? "";
      if (!env.KOREANPULSE_ADMIN_SECRET || provided !== env.KOREANPULSE_ADMIN_SECRET) {
        return json({ error: "forbidden" }, 403);
      }
      try {
        const result = await buildDaily(env);
        return json({ ok: true, ...result });
      } catch (exc) {
        const message = exc instanceof Error ? exc.message : String(exc);
        return json({ ok: false, error: message }, 500);
      }
    }

    if (request.method !== "GET") {
      return json({ error: "method not allowed" }, 405);
    }

    if (url.pathname === "/today") {
      const [html, freshness] = await Promise.all([
        env.DAILY.get(KV_HTML_LATEST),
        latestFreshness(env),
      ]);
      if (!html) {
        return new Response(
          renderEmptyState(
            "No daily snapshot is available yet. Builds run on the weekday cron at 16:30 KST.",
          ),
          { status: 200, headers: htmlHeaders(60) },
        );
      }
      return new Response(withFreshnessBanner(html, freshness), {
        status: 200,
        headers: htmlHeaders(300),
      });
    }

    if (url.pathname === "/today.json") {
      const data = await env.DAILY.get(KV_JSON_LATEST);
      if (!data) {
        return json(
          {
            error: "no snapshot available",
            freshness: computeFreshness(null, null, Date.now()),
          },
          404,
        );
      }
      return new Response(withFreshnessField(data), {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          // Short cache so the embedded freshness assessment can't drift far.
          "Cache-Control": "public, max-age=60",
        },
      });
    }

    const dateMatch = url.pathname.match(/^\/today\/(\d{4}-\d{2}-\d{2})$/);
    if (dateMatch) {
      const date = dateMatch[1];
      const html = await env.DAILY.get(`daily:html:${date}`);
      if (!html) return new Response(renderEmptyState(`No snapshot for ${date}.`), { status: 404, headers: htmlHeaders(300) });
      return new Response(html, { status: 200, headers: htmlHeaders(86400) });
    }

    return json({ error: "not found" }, 404);
  },
};

// Exported for the regression tests in test/ (last-known-good preservation).
export async function buildDaily(
  env: Env,
): Promise<{
  activists: number;
  foreign: number;
  top: number;
  takeaway: number;
  date: string;
  degraded: string[];
}> {
  // KST date — DART is filed in KST and the dashboard targets KOSPI close.
  const nowKst = new Date(Date.now() + 9 * 3600 * 1000);
  const date = nowKst.toISOString().slice(0, 10);

  // Single DART API call services both activist + foreign-flow streams.
  // 7-day window catches bursty 5%-rule filings without overwhelming the
  // page. Both streams sorted most-recent first. Major filings: last 1 day,
  // top 10 — the "what big companies actually said today" feed.
  const classified = await tryClassifiedFilings(env, 7);
  const top = await tryTopFilings(env, 1, 10);

  // Every stream failing means DART is down, not that KRX went quiet. Bail
  // before the KV writes below — they are unconditional, so continuing would
  // overwrite the last good snapshot with a blank one that reads exactly like
  // a quiet day, and nothing backs those keys up. Throwing keeps yesterday's
  // real data serving and restores `[cron] buildDaily FAILED`, which is the
  // only signal anyone can act on for a job that runs at 07:30 UTC untailed.
  if (!classified.ok && !top.ok) {
    throw new Error(
      "DART unavailable — every filing stream failed, refusing to overwrite " +
        `the last good snapshot. classified: ${classified.error} | top: ${top.error}`,
    );
  }

  const { activists, foreign_flows } = classified.ok
    ? classified.data
    : { activists: [], foreign_flows: [] };
  const topRaw = top.ok ? top.data : [];

  // Partial failure still ships, but labelled. An empty section and a section
  // we failed to fetch look identical once rendered, so the snapshot has to
  // carry which streams are missing.
  const degraded: string[] = [];
  if (!classified.ok) degraded.push("activist and foreign-holder filings");
  if (!top.ok) degraded.push("major filings");

  // Translate / summarise — bounded so the cron stays under the 30-second
  // free-tier CPU limit even on cold cache.
  const activistsEnriched = await enrichActivists(env, activists.slice(0, 5));
  const foreignEnriched = await enrichForeign(env, foreign_flows.slice(0, 5));
  const topEnriched = await enrichTop(env, topRaw.slice(0, 10));

  // Day's takeaway — 1–3 LLM-generated bullets summarising the most
  // material moves. Built from a compact digest so the LLM doesn't need
  // to chew through every field.
  const takeaway = await safeTakeaway(env, date, activistsEnriched, foreignEnriched, topEnriched);

  const snap: DailySnapshot = {
    schema_version: SNAPSHOT_SCHEMA_VERSION,
    date,
    generated_at: new Date().toISOString(),
    market: "KRX",
    takeaway,
    activist_filings: activistsEnriched,
    foreign_flows: foreignEnriched,
    top_filings: topEnriched,
    // Omitted entirely on a clean build so consumers can treat presence as the
    // signal, and so a normal snapshot's JSON is unchanged from schema v2.
    ...(degraded.length ? { degraded } : {}),
    attribution: ATTRIBUTION,
    data_sources: [
      { name: "DART (전자공시시스템)", url: "https://opendart.fss.or.kr/" },
    ],
    legal_notice:
      "Disclosure data sourced from the DART open API with attribution; each item links to the " +
      "original filing. Not investment advice — data and summaries only.",
  };

  const html = renderDaily(snap);
  const jsonStr = JSON.stringify(snap);

  const ttl = (parseInt(env.HISTORY_DAYS, 10) || 30) * 86400;
  try {
    await Promise.all([
      env.DAILY.put(KV_HTML_LATEST, html),
      env.DAILY.put(KV_JSON_LATEST, jsonStr),
      env.DAILY.put(`daily:html:${date}`, html, { expirationTtl: ttl }),
      env.DAILY.put(`daily:json:${date}`, jsonStr, { expirationTtl: ttl }),
    ]);
  } catch (exc) {
    // Distinguish "built fine but couldn't persist" from a DART/LLM failure
    // in the logs — the remediation is completely different.
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error(`[kv] snapshot write FAILED for ${date}: ${message}`);
    throw exc;
  }

  if (env.DISCORD_WEBHOOK_URL) {
    const result = await postToDiscord(env.DISCORD_WEBHOOK_URL, snap);
    if (!result.ok) {
      console.warn("discord push failed", result);
    }
  }

  return {
    activists: activistsEnriched.length,
    foreign: foreignEnriched.length,
    top: topEnriched.length,
    takeaway: takeaway.length,
    date,
    degraded,
  };
}

async function safeTakeaway(
  env: Env,
  date: string,
  activists: ActivistFilingEnriched[],
  foreign: ForeignFlowEnriched[],
  top: FilingEnriched[],
): Promise<string[]> {
  const digest = [
    ...foreign.map((f) => ({
      kind: "foreign" as const,
      filer: f.holder_label,
      corp: f.corp_name_ko,
      ticker: f.stock_code,
      title_en: f.title_en || f.title,
    })),
    ...activists.map((f) => ({
      kind: "activist" as const,
      filer: f.activist_label,
      corp: f.corp_name_ko,
      ticker: f.stock_code,
      title_en: f.title_en || f.title,
    })),
    ...top.slice(0, 5).map((f) => ({
      kind: "major" as const,
      corp: f.corp_name_ko,
      ticker: f.stock_code,
      title_en: f.title_en || f.title,
    })),
  ];
  if (digest.length === 0) return [];
  try {
    return await generateTakeaway(env, date, digest);
  } catch (exc) {
    console.warn("takeaway fallthrough", exc);
    return [];
  }
}

async function enrichActivists(
  env: Env,
  rows: Awaited<ReturnType<typeof fetchClassifiedFilings>>["activists"],
): Promise<ActivistFilingEnriched[]> {
  return Promise.all(
    rows.map(async (f) => ({
      ...f,
      corp_name_en: await safeCorpName(env, f.corp_name_ko),
      title_en: await safeTranslate(env, f.title),
      summary_en: await safeSummarise(env, f.title),
    })),
  );
}

async function enrichForeign(
  env: Env,
  rows: Awaited<ReturnType<typeof fetchClassifiedFilings>>["foreign_flows"],
): Promise<ForeignFlowEnriched[]> {
  return Promise.all(
    rows.map(async (f) => ({
      ...f,
      corp_name_en: await safeCorpName(env, f.corp_name_ko),
      title_en: await safeTranslate(env, f.title),
      summary_en: await safeSummarise(env, f.title),
    })),
  );
}

async function enrichTop(env: Env, rows: DartFiling[]): Promise<FilingEnriched[]> {
  return Promise.all(
    rows.map(async (f) => ({
      ...f,
      corp_name_en: await safeCorpName(env, f.corp_name_ko),
      title_en: await safeTranslate(env, f.title),
      // No summary for the long list — keeps OpenAI usage bounded.
      summary_en: undefined,
    })),
  );
}

async function safeTranslate(env: Env, text: string): Promise<string> {
  try {
    return await translateTitle(env, text);
  } catch (exc) {
    console.warn("translate fallthrough", exc);
    return ""; // render falls back to Korean title
  }
}

async function safeCorpName(env: Env, ko: string): Promise<string> {
  try {
    return await translateCorpName(env, ko);
  } catch (exc) {
    console.warn("corp name translate fallthrough", exc);
    return "";
  }
}

async function safeSummarise(env: Env, text: string): Promise<string | undefined> {
  try {
    return await summariseFiling(env, text);
  } catch (exc) {
    console.warn("summarise fallthrough", exc);
    return undefined;
  }
}

// DART-level wrappers. A single stream failing (Friday peak load, transient
// 5xx, UA redirect) shouldn't cost us the whole build — but the failure has to
// stay visible, because an empty DART result and a genuinely quiet KRX day are
// indistinguishable downstream. These report the outcome instead of swallowing
// it; buildDaily decides what to do with it.
type DartOutcome<T> = { ok: true; data: T } | { ok: false; error: string };

async function tryClassifiedFilings(
  env: Env,
  daysBack: number,
): Promise<DartOutcome<Awaited<ReturnType<typeof fetchClassifiedFilings>>>> {
  try {
    return { ok: true, data: await fetchClassifiedFilings(env, daysBack) };
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error(`[dart] fetchClassifiedFilings FAILED: ${message}`);
    return { ok: false, error: message };
  }
}

async function tryTopFilings(
  env: Env,
  daysBack: number,
  limit: number,
): Promise<DartOutcome<Awaited<ReturnType<typeof fetchTopFilings>>>> {
  try {
    return { ok: true, data: await fetchTopFilings(env, daysBack, limit) };
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error(`[dart] fetchTopFilings FAILED: ${message}`);
    return { ok: false, error: message };
  }
}

/** Freshness of the latest stored snapshot (KV read of the JSON copy). */
async function latestFreshness(env: Env): Promise<Freshness> {
  let snapshotDate: string | null = null;
  let generatedAt: string | null = null;
  try {
    const raw = await env.DAILY.get(KV_JSON_LATEST);
    if (raw) {
      const snap = JSON.parse(raw) as { date?: string; generated_at?: string };
      snapshotDate = snap.date ?? null;
      generatedAt = snap.generated_at ?? null;
    }
  } catch (exc) {
    console.error(
      `[freshness] could not read latest snapshot: ${exc instanceof Error ? exc.message : String(exc)}`,
    );
  }
  return computeFreshness(snapshotDate, generatedAt, Date.now());
}

/**
 * Serve-time augmentation: parse the stored snapshot and attach a `freshness`
 * object computed against the current clock. Falls back to the raw stored
 * bytes if the stored value is somehow unparseable.
 */
export function withFreshnessField(storedJson: string, nowMs = Date.now()): string {
  try {
    const snap = JSON.parse(storedJson) as { date?: string; generated_at?: string };
    const freshness = computeFreshness(snap.date ?? null, snap.generated_at ?? null, nowMs);
    return JSON.stringify({ ...snap, freshness });
  } catch {
    return storedJson;
  }
}

/**
 * Serve-time stale banner. Stored HTML is a static render, so the honesty
 * signal ("this page is NOT current") has to be injected per-request. Injects
 * right after <body> so it also works for snapshots rendered by older worker
 * versions.
 */
export function withFreshnessBanner(html: string, freshness: Freshness): string {
  if (freshness.state === "fresh") return html;
  const color =
    freshness.state === "pending"
      ? "border-sky-500/50 bg-sky-500/10 text-sky-200"
      : "border-red-500/50 bg-red-500/10 text-red-200";
  const label =
    freshness.state === "pending"
      ? "Today's build is running."
      : "This snapshot is stale.";
  const banner =
    `<div class="max-w-3xl mx-auto px-4 pt-6"><div class="rounded-lg border ${color} px-4 py-3 text-sm">` +
    `<strong class="font-semibold">${label}</strong> ` +
    `${escapeText(freshness.note)} <span class="opacity-70">(checked ${escapeText(
      freshness.checked_at,
    )})</span></div></div>`;
  return html.replace(/(<body[^>]*>)/i, `$1${banner}`);
}

function escapeText(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function htmlHeaders(maxAge: number): HeadersInit {
  return {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": `public, max-age=${maxAge}`,
  };
}

function renderEmptyState(message: string): string {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>koreanpulse / today</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>body { background: #0E1116; }</style>
</head>
<body class="text-stone-200 min-h-screen">
<div class="max-w-3xl mx-auto px-4 py-20 text-center">
<a href="/" class="text-amber-400 text-2xl font-semibold tracking-tight">koreanpulse</a>
<p class="text-stone-400 mt-6">${message.replace(/</g, "&lt;")}</p>
<p class="text-stone-500 text-sm mt-4"><a href="/" class="hover:text-stone-300">← back</a></p>
</div></body></html>`;
}
