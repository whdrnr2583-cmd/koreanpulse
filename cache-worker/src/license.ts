/**
 * License validation hop. Calls our own koreanpulse-webhook process at
 * `/v1/validate` with an HMAC-signed body so the webhook doesn't have to
 * trust this Worker's IP, and caches successful validations for 60s in the
 * per-colocation Cache API.
 *
 * The webhook is the only thing that touches Postgres. We never connect
 * directly from the Worker — keeps the architecture single-Postgres-client
 * and avoids Hyperdrive / D1.
 */

import type { Env } from "./index";

export interface ValidationResult {
  ok: boolean;
  plan?: string;
  reason?: string;       // human-readable
  code?: string;         // stable code: "missing" | "invalid" | "inactive" | "quota_exceeded" | "config"
  httpStatus?: number;   // suggested HTTP status to return to the caller
}

const TTL_SECONDS = 60;

export async function validateLicense(
  licenseKey: string,
  env: Env,
  ctx: ExecutionContext,
): Promise<ValidationResult> {
  const keyHash = await sha256Hex(licenseKey);
  // Synthetic URL — the Cache API keys on the request URL, never sent
  // anywhere. Hashing the license key keeps it out of cache metadata.
  const cacheKey = new Request(
    `https://cache.koreanpulse.internal/license/${keyHash}`,
    { method: "GET" },
  );
  const cache = caches.default;

  const cached = await cache.match(cacheKey);
  if (cached) {
    return (await cached.json()) as ValidationResult;
  }

  const body = JSON.stringify({ license_key: licenseKey });
  const signature = await hmacSha256Hex(env.WEBHOOK_SHARED_SECRET, body);

  let resp: Response;
  try {
    resp = await fetch(env.WEBHOOK_VALIDATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Cache-Signature": signature,
      },
      body,
    });
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error("validate fetch failed", { message });
    return { ok: false, reason: "license backend unreachable", httpStatus: 503 };
  }

  if (!resp.ok) {
    return {
      ok: false,
      reason: `validate ${resp.status}`,
      httpStatus: resp.status === 401 ? 500 : 503,
    };
  }

  const result = (await resp.json()) as ValidationResult;

  // Only cache successful validations. Failures should re-hit the backend
  // immediately so a cancellation / quota reset is picked up promptly.
  if (result.ok) {
    const cacheResp = new Response(JSON.stringify(result), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": `public, max-age=${TTL_SECONDS}`,
      },
    });
    ctx.waitUntil(cache.put(cacheKey, cacheResp));
  }

  return result;
}

async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return bufToHex(hash);
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
  return bufToHex(sig);
}

function bufToHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
