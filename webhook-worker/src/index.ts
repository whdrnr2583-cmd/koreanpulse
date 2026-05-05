/**
 * koreanpulse-webhook entry point.
 *
 * Endpoints:
 *   GET  /health                     → liveness
 *   POST /webhook/lemonsqueezy       → LS billing webhook
 *   POST /v1/validate                → license validate (Worker-to-Worker)
 *
 * Replaces the old Lightsail FastAPI deployment. Whole stack is now
 * 100% Cloudflare:
 *   webhook-worker (this) + cache-worker + daily-worker + Vercel landing.
 *   D1 (this) replaces Postgres.
 */

import { handleEvent, verifyLsSignature, type Env } from "./lemonsqueezy";
import { validateAndCharge } from "./license";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/health") {
      return json({ status: "ok" });
    }

    if (request.method !== "POST") {
      return json({ error: "method not allowed" }, 405);
    }

    if (url.pathname === "/webhook/lemonsqueezy") {
      return await handleLemonSqueezy(request, env);
    }

    if (url.pathname === "/v1/validate") {
      return await handleValidate(request, env);
    }

    return json({ error: "not found" }, 404);
  },
};

async function handleLemonSqueezy(request: Request, env: Env): Promise<Response> {
  const secret = (env.LEMONSQUEEZY_WEBHOOK_SECRET ?? "").trim();
  if (!secret) {
    console.error("LEMONSQUEEZY_WEBHOOK_SECRET not set");
    return json({ error: "server not configured" }, 500);
  }

  const signature =
    request.headers.get("x-signature") ||
    request.headers.get("X-Signature") ||
    "";
  const body = await request.text();

  const ok = await verifyLsSignature(body, signature, secret);
  if (!ok) {
    console.warn("rejected webhook with bad signature");
    return json({ error: "invalid signature" }, 401);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    return json({ error: `invalid JSON: ${message}` }, 400);
  }

  try {
    const result = await handleEvent(env, payload);
    // Always 200 unless we want LS to retry. Failures surface in body.
    return json(result, 200);
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error("handleEvent failed", { message });
    // 500 lets LS retry — only return this on genuine infra problems
    // (D1 down). Application-level errors come back as ok:false in body
    // from handleEvent itself.
    return json({ ok: false, action: "error", message }, 500);
  }
}

async function handleValidate(request: Request, env: Env): Promise<Response> {
  const sharedSecret = (env.KOREANPULSE_CACHE_SHARED_SECRET ?? "").trim();
  if (!sharedSecret) {
    console.error("KOREANPULSE_CACHE_SHARED_SECRET not set");
    return json({ error: "validate not configured" }, 500);
  }

  const signature =
    request.headers.get("x-cache-signature") ||
    request.headers.get("X-Cache-Signature") ||
    "";
  const body = await request.text();

  const expected = await hmacSha256Hex(sharedSecret, body);
  if (!constantTimeEq(expected, signature.trim())) {
    console.warn("rejected validate with bad signature");
    return json({ error: "invalid signature" }, 401);
  }

  let payload: { license_key?: string };
  try {
    payload = JSON.parse(body);
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    return json({ error: `invalid JSON: ${message}` }, 400);
  }

  const result = await validateAndCharge(env.DB, payload.license_key, 1);
  return json(result, 200);
}

// ── helpers ───────────────────────────────────────────────────────────────

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function hmacSha256Hex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function constantTimeEq(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}
