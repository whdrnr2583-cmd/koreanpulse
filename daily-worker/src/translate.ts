/**
 * OpenAI translation/summary client — Worker-side.
 *
 * The daily cron generates ~5–10 English titles + 3–5 short summaries
 * once per weekday. Cost: < $0.20/month. Cache hits inside one cron run
 * are de-duplicated by KV — same title submitted twice in the same day
 * returns from cache.
 */

import type { Env } from "./index";

const SYSTEM_TRANSLATE =
  "Translate the Korean financial / industry text to English. " +
  "Preserve company names in their official English form when widely known " +
  "(e.g. '삼성전자' → 'Samsung Electronics'); otherwise transliterate and " +
  "append the Korean in parentheses on first use. Output the translation only.";

const SYSTEM_CORP_NAME =
  "Return the official English name of the Korean company. " +
  "For widely-known names use the standard form ('삼성전자' → 'Samsung Electronics', " +
  "'셀트리온' → 'Celltrion', 'SK하이닉스' → 'SK Hynix', '네이버' → 'NAVER', " +
  "'카카오' → 'Kakao', 'LG에너지솔루션' → 'LG Energy Solution', " +
  "'HD현대중공업' → 'HD Hyundai Heavy Industries'). " +
  "For lesser-known names, transliterate without parentheses or quotes. " +
  "Output the company name only — no commentary, no Korean.";

const SYSTEM_SUMMARIZE_FILING =
  "You are a financial-industry analyst writing for English-speaking " +
  "fund analysts. In <= 80 English words, summarise this Korean filing. " +
  "Lead with the single most material fact. Preserve numbers exactly. " +
  "Do not add commentary or interpretation beyond the filing's content.";

const MAX_INPUT_CHARS = 6000;
const CACHE_PREFIX = "translate:";

async function sha256Short(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
}

async function callOpenAI(
  env: Env,
  system: string,
  user: string,
  maxTokens: number,
): Promise<string> {
  const body: Record<string, unknown> = {
    model: env.LLM_MODEL,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user.slice(0, MAX_INPUT_CHARS) },
    ],
    max_completion_tokens: maxTokens,
  };
  // gpt-5 family is a reasoning model — without reasoning_effort="minimal"
  // the reasoning_tokens silently consume the max_completion_tokens budget,
  // returning visible content as an empty string. Setting minimal disables
  // chain-of-thought so the full budget goes to user-facing text.
  if (typeof env.LLM_MODEL === "string" && env.LLM_MODEL.startsWith("gpt-5")) {
    body.reasoning_effort = "minimal";
  }
  // Cloudflare AI Gateway proxy — bypasses OpenAI's region block on KR/HK
  // CF colos. Same OpenAI key, same payload, just routed through CF infra.
  const resp = await fetch(
    "https://gateway.ai.cloudflare.com/v1/520ed8d88fdd95e30af7d0a0e81c1706/koreanpulse/openai/chat/completions",
    {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    },
  );
  if (!resp.ok) {
    const errBody = (await resp.text()).slice(0, 200);
    throw new Error(`OpenAI ${resp.status}: ${errBody}`);
  }
  const data = (await resp.json()) as {
    choices?: { message?: { content?: string }; finish_reason?: string }[];
  };
  const out = (data.choices?.[0]?.message?.content ?? "").trim();
  if (!out) {
    // Throw rather than cache empty — safe* wrappers convert to "" without
    // poisoning KV. Includes finish_reason for diagnosis.
    const fr = data.choices?.[0]?.finish_reason ?? "unknown";
    throw new Error(`OpenAI empty content (finish_reason=${fr})`);
  }
  return out;
}

export async function translateTitle(env: Env, koTitle: string): Promise<string> {
  if (!koTitle.trim()) return "";
  const key = `${CACHE_PREFIX}t:${env.LLM_MODEL}:${await sha256Short(koTitle)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_TRANSLATE, koTitle, 1024);
  // Translations of filing titles are stable — cache 90 days.
  await env.DAILY.put(key, out, { expirationTtl: 60 * 60 * 24 * 90 });
  return out;
}

export async function translateCorpName(env: Env, nameKo: string): Promise<string> {
  if (!nameKo.trim()) return "";
  const key = `${CACHE_PREFIX}c:${env.LLM_MODEL}:${await sha256Short(nameKo)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_CORP_NAME, nameKo, 512);
  // Company-name translations are stable forever — no TTL.
  await env.DAILY.put(key, out);
  return out;
}

export async function summariseFiling(env: Env, koTitle: string): Promise<string> {
  if (!koTitle.trim()) return "";
  const key = `${CACHE_PREFIX}s:${env.LLM_MODEL}:${await sha256Short(koTitle)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_SUMMARIZE_FILING, koTitle, 1024);
  await env.DAILY.put(key, out, { expirationTtl: 60 * 60 * 24 * 90 });
  return out;
}

/**
 * Daily takeaway — what's the most material thing on this snapshot?
 *
 * Called once per cron tick on a small JSON digest of the day's foreign /
 * activist / major filings. Output is 1–3 short bullets in English aimed
 * at a foreign-retail / boutique-analyst reader who has 30 seconds.
 *
 * Cached per (date + digest hash) so a manual /admin/rebuild doesn't burn
 * extra OpenAI calls if the underlying data hasn't moved.
 */
const SYSTEM_TAKEAWAY =
  "You are a precise financial-industry analyst writing for English-speaking " +
  "investors and analysts watching Korean equities. Read the JSON digest of " +
  "today's KRX disclosures and write 1–3 short bullets (≤25 words each) on " +
  "the single most material moves. Lead with foreign-holder filings if they " +
  "exist. Mention specific names (KCGI / BlackRock / Norges / etc.) and " +
  "tickers when present. No commentary, no investment advice — factual " +
  "extraction only. Output bullets as plain text, one per line, no markdown. " +
  "Write every bullet in English. Company names may keep their Korean name " +
  "in parentheses.";

// Used for the single retry after a Korean-language answer.
const SYSTEM_TAKEAWAY_STRICT =
  SYSTEM_TAKEAWAY +
  " IMPORTANT: a previous answer was written in Korean, which is not " +
  "acceptable. Respond in English only. Do not output Hangul except for a " +
  "Korean company name placed in parentheses after its English name.";

/**
 * A bullet is treated as Korean when more than this share of its letters are
 * Hangul syllables. A bullet that merely carries a Korean company name in
 * parentheses normally sits below it; a bullet written in Korean normally sits
 * above it. It is a heuristic with known limits: a Korean sentence with long
 * English proper names can fall under the threshold and be missed, and an
 * English bullet with a long Hangul company name and little other English can
 * exceed it and be rejected.
 */
export const KOREAN_RATIO_THRESHOLD = 0.4;

/**
 * Share of a text's letters (whitespace, digits and symbols excluded) that
 * are Hangul syllables. 0 when the text has no letters.
 */
export function koreanRatio(text: string): number {
  const letters = text.match(/\p{L}/gu);
  if (!letters || letters.length === 0) return 0;
  const hangul = text.match(/[\uAC00-\uD7A3]/g);
  return (hangul ? hangul.length : 0) / letters.length;
}

export function hasKoreanBullet(bullets: string[]): boolean {
  return bullets.some((b) => koreanRatio(b) > KOREAN_RATIO_THRESHOLD);
}

function parseBullets(raw: string): string[] {
  // Strip markdown, drop empties, cap at 3.
  return raw
    .split("\n")
    .map((line) => line.replace(/^\s*[-*•]\s*/, "").trim())
    .filter((line) => line.length > 0)
    .slice(0, 3);
}

interface TakeawayDigestItem {
  kind: "foreign" | "activist" | "major";
  filer?: string;
  corp?: string;
  ticker?: string | null;
  title_en: string;
}

export async function generateTakeaway(
  env: Env,
  date: string,
  digest: TakeawayDigestItem[],
): Promise<string[]> {
  if (digest.length === 0) return [];

  const digestJson = JSON.stringify(digest);
  const key = `${CACHE_PREFIX}td:${date}:${await sha256Short(digestJson)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) {
    try {
      const parsed = JSON.parse(cached) as string[];
      // Entries cached before the English-only check may hold Korean bullets.
      if (!hasKoreanBullet(parsed)) return parsed;
    } catch {
      // fall through to regenerate
    }
  }

  const user = `Date: ${date}\n\nDigest:\n${digestJson}`;
  let bullets = parseBullets(await callOpenAI(env, SYSTEM_TAKEAWAY, user, 1024));

  // The page is English-only. If the model answered in Korean, retry once
  // with a stronger instruction; if it still does, publish no takeaway
  // rather than a Korean one.
  if (hasKoreanBullet(bullets)) {
    bullets = parseBullets(await callOpenAI(env, SYSTEM_TAKEAWAY_STRICT, user, 1024));
    if (hasKoreanBullet(bullets)) return [];
  }

  // Never cache an empty result — the next build should be able to retry.
  if (bullets.length > 0) {
    await env.DAILY.put(key, JSON.stringify(bullets), {
      expirationTtl: 60 * 60 * 24 * 30,
    });
  }
  return bullets;
}
