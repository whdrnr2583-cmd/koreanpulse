/**
 * KV-backed translation/summary cache + OpenAI fallback.
 *
 * Cache key shape: `<kind>:<sha256(provider:model:text)[0..32]>`.
 * Provider+model are folded into the digest so swapping models doesn't
 * poison cache (mirrors the Python translator's behavior).
 *
 * Cache lifetime:
 *   translate  → no expiry; same Korean filing title is identical forever
 *   summarize  → 30 days; less reuse + content can drift if the source
 *                document is amended (DART types A/B can be re-filed).
 */

import type { Env } from "./index";

export interface TranslateRequest {
  kind: "translate" | "summarize";
  text: string;
  attribution?: string;
}

export interface TranslateResponse {
  output: string;
  cached: boolean;
  provider: string;
  model: string;
}

const SYSTEM_TRANSLATE =
  "You are a precise translator of Korean financial / industry text into " +
  "English. Translate faithfully. Preserve company names in their official " +
  "English form when widely known (e.g. '삼성전자' → 'Samsung Electronics'); " +
  "otherwise transliterate and append the Korean in parentheses on first use. " +
  "Output the translation only, no commentary.";

const SYSTEM_SUMMARIZE =
  "You are a precise financial-industry analyst writing for English-speaking " +
  "fund analysts. Summarize the Korean text in <=200 English words. " +
  "Lead with the single most material fact. Preserve numbers exactly. " +
  "If a number is ambiguous (KRW vs USD, billions vs millions), say so. " +
  "End with one line: 'Source: <attribution>'. No commentary beyond the summary.";

const SUMMARY_TTL_SECONDS = 60 * 60 * 24 * 30;

export async function translateOrSummarize(
  req: TranslateRequest,
  env: Env,
): Promise<TranslateResponse> {
  const provider = env.LLM_PROVIDER || "openai";
  const model = env.LLM_MODEL || "gpt-5-mini";
  const maxChars = parseInt(env.MAX_INPUT_CHARS || "6000", 10);
  const truncated = req.text.slice(0, isFinite(maxChars) ? maxChars : 6000);

  const cacheKey = await buildCacheKey(req.kind, provider, model, truncated);

  const cached = await env.TRANSLATIONS.get(cacheKey);
  if (cached !== null) {
    return { output: cached, cached: true, provider, model };
  }

  const system = req.kind === "translate" ? SYSTEM_TRANSLATE : SYSTEM_SUMMARIZE;
  const userMessage =
    req.kind === "summarize"
      ? `${truncated}\n\n---\nAttribution: ${req.attribution ?? ""}`
      : truncated;

  const output = await callOpenAI(system, userMessage, model, env);

  const putOpts: KVNamespacePutOptions =
    req.kind === "summarize" ? { expirationTtl: SUMMARY_TTL_SECONDS } : {};
  await env.TRANSLATIONS.put(cacheKey, output, putOpts);

  return { output, cached: false, provider, model };
}

async function callOpenAI(
  system: string,
  user: string,
  model: string,
  env: Env,
): Promise<string> {
  const body: Record<string, unknown> = {
    model,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    // GPT-5 series uses max_completion_tokens, not max_tokens.
    max_completion_tokens: 1024,
  };
  // gpt-5 family is a reasoning model — without minimal effort the
  // reasoning_tokens silently consume the budget, returning empty content.
  if (model.startsWith("gpt-5")) {
    body.reasoning_effort = "minimal";
  }
  // Cloudflare AI Gateway proxy — bypasses OpenAI region block on KR/HK
  // CF colos.
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
    const fr = data.choices?.[0]?.finish_reason ?? "unknown";
    throw new Error(`OpenAI empty content (finish_reason=${fr})`);
  }
  return out;
}

async function buildCacheKey(
  kind: string,
  provider: string,
  model: string,
  text: string,
): Promise<string> {
  const data = new TextEncoder().encode(`${provider}:${model}:${text}`);
  const hash = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `${kind}:${hex.slice(0, 32)}`;
}
