/**
 * koreanpulse-cache — translation/summary cache fronted by a license gate.
 *
 * Endpoints:
 *   GET  /health                    → liveness probe
 *   POST /v1/translate              → { kind, text, attribution?, license_key }
 *
 * Flow per /v1/translate request:
 *   1. validateLicense() — HMAC-signed call to koreanpulse-webhook,
 *      cached for 60s in the per-colo Cache API (≈ 1 validate/min/colo
 *      of Postgres pressure regardless of request volume).
 *   2. KV lookup for the (kind, provider, model, text) tuple. Hit → return.
 *   3. OpenAI Chat Completions call with the appropriate system prompt.
 *   4. Write the result back to KV with an indefinite TTL for translations
 *      and a 30-day TTL for summaries (summaries are per-document, less reuse).
 *
 * Errors return JSON with a stable shape: { error: string }. We never
 * surface the OpenAI error body verbatim — the user paid for a translation,
 * not an OpenAI billing diagnostic.
 */

import { translateOrSummarize, type TranslateRequest } from "./translate";
import { validateLicense } from "./license";

export interface Env {
  TRANSLATIONS: KVNamespace;
  WEBHOOK_VALIDATE_URL: string;
  LLM_PROVIDER: string;
  LLM_MODEL: string;
  MAX_INPUT_CHARS: string;
  OPENAI_API_KEY: string;
  WEBHOOK_SHARED_SECRET: string;
}

interface RequestBody {
  kind?: "translate" | "summarize";
  text?: string;
  attribution?: string;
  license_key?: string;
}

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "ok" });
    }

    if (request.method !== "POST" || url.pathname !== "/v1/translate") {
      return json({ error: "not found" }, 404);
    }

    let body: RequestBody;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid JSON body" }, 400);
    }

    const kind = body.kind;
    const text = (body.text ?? "").trim();
    const licenseKey = (body.license_key ?? "").trim();

    if (kind !== "translate" && kind !== "summarize") {
      return json({ error: "kind must be 'translate' or 'summarize'" }, 400);
    }
    if (!text) {
      return json({ error: "text is required" }, 400);
    }
    if (!licenseKey) {
      return json({ error: "license_key is required" }, 401);
    }
    if (kind === "summarize" && !body.attribution) {
      return json({ error: "attribution is required for summarize" }, 400);
    }

    const validation = await validateLicense(licenseKey, env, ctx);
    if (!validation.ok) {
      return json(
        {
          error: validation.reason ?? "license invalid",
          code: validation.code,
        },
        validation.httpStatus ?? 402,
      );
    }

    const tr: TranslateRequest = {
      kind,
      text,
      attribution: body.attribution,
    };

    try {
      const result = await translateOrSummarize(tr, env);
      return json(result);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      // Don't leak provider error bodies; log for ops, return generic.
      console.error("translate failed", { kind, message });
      return json({ error: "translation backend failed" }, 502);
    }
  },
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
