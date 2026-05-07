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

export interface Env {
  DAILY: KVNamespace;
  DART_API_KEY: string;
  DART_API_BASE: string;
  OPENAI_API_KEY: string;
  LLM_MODEL: string;
  SITE_URL: string;
  HISTORY_DAYS: string;
  DISCORD_WEBHOOK_URL?: string;
}

const KV_HTML_LATEST = "daily:html:latest";
const KV_JSON_LATEST = "daily:json:latest";
const ATTRIBUTION = "Source: 금융감독원 전자공시시스템 DART (https://dart.fss.or.kr/)";

export default {
  async scheduled(
    _event: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    ctx.waitUntil(buildDaily(env));
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "ok" });
    }

    if (request.method !== "GET") {
      return json({ error: "method not allowed" }, 405);
    }

    if (url.pathname === "/today") {
      const html = await env.DAILY.get(KV_HTML_LATEST);
      if (!html) {
        return new Response(
          renderEmptyState("Daily build hasn't run yet — first cron at KST 16:30 on weekdays."),
          { status: 200, headers: htmlHeaders(60) },
        );
      }
      return new Response(html, { status: 200, headers: htmlHeaders(300) });
    }

    if (url.pathname === "/today.json") {
      const data = await env.DAILY.get(KV_JSON_LATEST);
      if (!data) {
        return json({ error: "daily build pending" }, 404);
      }
      return new Response(data, {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=300",
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

    // Manual trigger for ops / first-time setup. Protected by SHARED secret
    // header so casual visitors can't spam OpenAI from our key.
    if (url.pathname === "/admin/rebuild") {
      const provided = request.headers.get("x-admin-key") ?? "";
      if (!env.DART_API_KEY || provided !== env.DART_API_KEY) {
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

    return json({ error: "not found" }, 404);
  },
};

async function buildDaily(
  env: Env,
): Promise<{ activists: number; foreign: number; top: number; takeaway: number; date: string }> {
  // KST date — DART is filed in KST and the dashboard targets KOSPI close.
  const nowKst = new Date(Date.now() + 9 * 3600 * 1000);
  const date = nowKst.toISOString().slice(0, 10);

  // Single DART API call services both activist + foreign-flow streams.
  // 7-day window catches bursty 5%-rule filings without overwhelming the
  // page. Both streams sorted most-recent first.
  const { activists, foreign_flows } = await fetchClassifiedFilings(env, 7);

  // Major filings: last 1 day, top 10 — the "what big companies actually
  // said today" feed.
  const topRaw = await fetchTopFilings(env, 1, 10);

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
    attribution: ATTRIBUTION,
    data_sources: [
      { name: "DART (전자공시시스템)", url: "https://opendart.fss.or.kr/" },
    ],
    legal_notice:
      "DART data is public; redistributed with attribution. No investment advice — data + summary only.",
  };

  const html = renderDaily(snap);
  const jsonStr = JSON.stringify(snap);

  const ttl = (parseInt(env.HISTORY_DAYS, 10) || 30) * 86400;
  await Promise.all([
    env.DAILY.put(KV_HTML_LATEST, html),
    env.DAILY.put(KV_JSON_LATEST, jsonStr),
    env.DAILY.put(`daily:html:${date}`, html, { expirationTtl: ttl }),
    env.DAILY.put(`daily:json:${date}`, jsonStr, { expirationTtl: ttl }),
  ]);

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
