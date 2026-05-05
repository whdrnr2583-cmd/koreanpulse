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
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: env.LLM_MODEL,
      messages: [
        { role: "system", content: system },
        { role: "user", content: user.slice(0, MAX_INPUT_CHARS) },
      ],
      max_completion_tokens: maxTokens,
    }),
  });
  if (!resp.ok) {
    const errBody = (await resp.text()).slice(0, 200);
    throw new Error(`OpenAI ${resp.status}: ${errBody}`);
  }
  const data = (await resp.json()) as {
    choices?: { message?: { content?: string } }[];
  };
  return (data.choices?.[0]?.message?.content ?? "").trim();
}

export async function translateTitle(env: Env, koTitle: string): Promise<string> {
  if (!koTitle.trim()) return "";
  const key = `${CACHE_PREFIX}t:${env.LLM_MODEL}:${await sha256Short(koTitle)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_TRANSLATE, koTitle, 256);
  // Translations of filing titles are stable — cache 90 days.
  await env.DAILY.put(key, out, { expirationTtl: 60 * 60 * 24 * 90 });
  return out;
}

export async function translateCorpName(env: Env, nameKo: string): Promise<string> {
  if (!nameKo.trim()) return "";
  const key = `${CACHE_PREFIX}c:${env.LLM_MODEL}:${await sha256Short(nameKo)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_CORP_NAME, nameKo, 128);
  // Company-name translations are stable forever — no TTL.
  await env.DAILY.put(key, out);
  return out;
}

export async function summariseFiling(env: Env, koTitle: string): Promise<string> {
  if (!koTitle.trim()) return "";
  const key = `${CACHE_PREFIX}s:${env.LLM_MODEL}:${await sha256Short(koTitle)}`;
  const cached = await env.DAILY.get(key);
  if (cached !== null) return cached;

  const out = await callOpenAI(env, SYSTEM_SUMMARIZE_FILING, koTitle, 256);
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
  "extraction only. Output bullets as plain text, one per line, no markdown.";

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
      return JSON.parse(cached) as string[];
    } catch {
      // fall through to regenerate
    }
  }

  const user = `Date: ${date}\n\nDigest:\n${digestJson}`;
  const raw = await callOpenAI(env, SYSTEM_TAKEAWAY, user, 256);

  // Parse to bullets — strip markdown, drop empties, cap at 3.
  const bullets = raw
    .split("\n")
    .map((line) => line.replace(/^\s*[-*•]\s*/, "").trim())
    .filter((line) => line.length > 0)
    .slice(0, 3);

  await env.DAILY.put(key, JSON.stringify(bullets), {
    expirationTtl: 60 * 60 * 24 * 30,
  });
  return bullets;
}
