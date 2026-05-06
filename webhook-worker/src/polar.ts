/**
 * Polar webhook handling. Standard Webhooks spec
 * (https://www.standardwebhooks.com/) — same envelope every Polar tenant ships.
 *
 * Flow per webhook:
 *   1. Verify signature with `webhook-id` / `webhook-timestamp` / `webhook-signature`.
 *      Polar secret format: `polar_whs_<base64>` — strip prefix, base64-decode
 *      to get the raw HMAC key, then HMAC-SHA256 over `${id}.${timestamp}.${body}`,
 *      base64-encode, prefix with `v1,`. Polar may rotate, so the header
 *      contains space-separated `v1,<sig>` entries — match any.
 *   2. JSON parse — payload shape is `{ type, data }` (NOT `data.attributes`
 *      like Lemon Squeezy).
 *   3. Idempotency check via D1 `webhook_events.webhook_id` PK
 *      (webhook-id header is the dedup key).
 *   4. Dispatch on `type` (e.g. `subscription.created`, `subscription.active`).
 *   5. Same D1 `licenses` upsert as the LS path — Polar source is just a
 *      provider tag in metadata.
 */

import type { D1Database } from "@cloudflare/workers-types";
import {
  findByEmail,
  issueLicenseKey,
  markEventSeen,
  upsertLicense,
  type License,
  type Plan,
} from "./license";

export interface PolarEnv {
  DB: D1Database;
  POLAR_WEBHOOK_SECRET: string;
  POLAR_PRODUCT_SOLO?: string;
  POLAR_PRODUCT_ANALYST?: string;
  POLAR_PRODUCT_DESK?: string;
}

export interface HandlerResult {
  ok: boolean;
  action: string;
  license_key?: string;
  message?: string;
}

const ALLOWED_ROLES = new Set([
  "analyst", "rotator", "diaspora", "journalist", "developer", "other",
]);

function readProductMap(env: PolarEnv): Map<string, Plan> {
  const m = new Map<string, Plan>();
  const pairs: [string | undefined, Plan][] = [
    [env.POLAR_PRODUCT_SOLO, "solo"],
    [env.POLAR_PRODUCT_ANALYST, "analyst"],
    [env.POLAR_PRODUCT_DESK, "desk"],
  ];
  for (const [pid, plan] of pairs) {
    const trimmed = (pid ?? "").trim();
    if (trimmed) m.set(trimmed, plan);
  }
  return m;
}

// ── Signature verification (Standard Webhooks: v1,base64-HMAC-SHA256) ──────

export async function verifyPolarSignature(
  body: string,
  webhookId: string,
  webhookTimestamp: string,
  signatureHeader: string,
  secret: string,
): Promise<boolean> {
  if (!signatureHeader || !secret || !webhookId || !webhookTimestamp) {
    return false;
  }
  const keyBytes = decodePolarSecret(secret);
  if (!keyBytes) return false;

  const message = `${webhookId}.${webhookTimestamp}.${body}`;
  const expected = await hmacSha256Base64(keyBytes, message);

  // Header may carry several `v1,<sig>` entries separated by spaces (rotation).
  const provided = signatureHeader
    .split(" ")
    .map((s) => s.trim())
    .filter((s) => s.startsWith("v1,"))
    .map((s) => s.slice(3));

  for (const sig of provided) {
    if (constantTimeEq(sig, expected)) return true;
  }
  return false;
}

function decodePolarSecret(secret: string): Uint8Array | null {
  // `polar_whs_<base64>` — strip prefix.
  const trimmed = secret.trim();
  const stripped = trimmed.startsWith("polar_whs_")
    ? trimmed.slice("polar_whs_".length)
    : trimmed.startsWith("whsec_")
    ? trimmed.slice("whsec_".length)
    : trimmed;
  try {
    return base64DecodeUrlSafe(stripped);
  } catch {
    return null;
  }
}

function base64DecodeUrlSafe(s: string): Uint8Array {
  // Tolerate base64url variants — Polar emits standard base64, but some
  // tenants/users hand-paste url-safe variants.
  const normal = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = normal.length % 4 === 0 ? "" : "=".repeat(4 - (normal.length % 4));
  const decoded = atob(normal + pad);
  const out = new Uint8Array(decoded.length);
  for (let i = 0; i < decoded.length; i++) out[i] = decoded.charCodeAt(i);
  return out;
}

async function hmacSha256Base64(keyBytes: Uint8Array, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  const bytes = new Uint8Array(sig);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function constantTimeEq(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

// ── Field extractors ───────────────────────────────────────────────────────

function extractEmail(data: Record<string, unknown>): string {
  // Polar payloads stamp the customer/user object directly on data. Subscription
  // events carry `customer.email`; some events may carry `user.email` or a
  // top-level `customer_email`.
  const customer = (data.customer ?? {}) as Record<string, unknown>;
  const user = (data.user ?? {}) as Record<string, unknown>;
  const v = (customer.email
    ?? user.email
    ?? data.customer_email
    ?? data.email
    ?? "") as string;
  return String(v).trim().toLowerCase();
}

function extractProductId(data: Record<string, unknown>): string | undefined {
  if (data.product_id) return String(data.product_id);
  const product = (data.product ?? {}) as Record<string, unknown>;
  if (product && typeof product === "object" && "id" in product) {
    return String(product.id);
  }
  return undefined;
}

function extractStatus(data: Record<string, unknown>): string {
  return String(data.status ?? "").trim();
}

function extractSelfDescription(
  data: Record<string, unknown>,
): string | undefined {
  // Polar stashes checkout custom fields on `metadata` or `custom_field_data`.
  const candidates: unknown[] = [];

  const meta = (data.metadata ?? {}) as Record<string, unknown>;
  if (meta && typeof meta === "object") candidates.push(meta.role);

  const cfd = (data.custom_field_data ?? {}) as Record<string, unknown>;
  if (cfd && typeof cfd === "object") candidates.push(cfd.role);

  for (const c of candidates) {
    if (!c) continue;
    const s = String(c).trim().toLowerCase();
    if (!s) continue;
    return ALLOWED_ROLES.has(s) ? s : "other";
  }
  return undefined;
}

// ── Event dispatch ─────────────────────────────────────────────────────────

export async function handlePolarEvent(
  env: PolarEnv,
  payload: any,
  webhookId: string,
): Promise<HandlerResult> {
  const eventType = String(payload?.type ?? "").trim();
  const data = (payload?.data ?? {}) as Record<string, unknown>;
  const email = extractEmail(data);
  const productId = extractProductId(data);
  const selfDescription = extractSelfDescription(data);

  // Idempotency. Dedup by Polar's webhook-id header (each delivery has a
  // unique id even on retry).
  if (webhookId) {
    const existing = await env.DB
      .prepare("SELECT 1 FROM webhook_events WHERE webhook_id = ?")
      .bind(webhookId)
      .first();
    if (existing) {
      return {
        ok: true,
        action: "duplicate_ignored",
        message: `already processed ${webhookId}`,
      };
    }
  }

  let result: HandlerResult;

  switch (eventType) {
    case "subscription.created":
    case "subscription.active":
      result = await onSubscriptionActive(env, { email, productId, data, selfDescription });
      break;
    case "subscription.updated":
      result = await onSubscriptionUpdated(env, { email, productId, data });
      break;
    case "subscription.canceled":
    case "subscription.revoked":
      result = await onSubscriptionInactive(env, { email, data });
      break;
    default:
      result = {
        ok: true,
        action: "ignored",
        message: `no handler for type=${eventType}`,
      };
  }

  if (webhookId && result.ok) {
    await markEventSeen(env.DB, webhookId, eventType, {
      license_key: result.license_key,
      action: result.action,
      note: result.message,
    });
  }

  return result;
}

interface SubArgs {
  email: string;
  productId?: string;
  data: Record<string, unknown>;
  selfDescription?: string;
}

async function onSubscriptionActive(env: PolarEnv, a: SubArgs): Promise<HandlerResult> {
  if (!a.email) return { ok: false, action: "error", message: "missing email" };
  const plan = readProductMap(env).get(a.productId ?? "");
  if (!plan) {
    return {
      ok: false,
      action: "error",
      message: `unknown product_id=${a.productId}; configure POLAR_PRODUCT_*`,
    };
  }

  const existing = await findByEmail(env.DB, a.email);
  const status = extractStatus(a.data);
  const subId = String(a.data.id ?? "");

  if (existing) {
    existing.plan = plan;
    existing.active = true;
    existing.metadata = {
      ...existing.metadata,
      polar_subscription_id: subId,
      polar_product_id: a.productId,
      polar_status: status,
      provider: "polar",
    };
    if (a.selfDescription) {
      existing.metadata.self_description = a.selfDescription;
    }
    await upsertLicense(env.DB, existing);
    return {
      ok: true,
      action: "upgraded",
      license_key: existing.key,
      message: `existing license upgraded to ${plan} (polar)`,
    };
  }

  const now = new Date().toISOString();
  const lic: License = {
    key: issueLicenseKey(),
    plan,
    customer_email: a.email,
    active: true,
    created_at: now,
    period_calls: 0,
    period_started_at: now,
    metadata: {
      provider: "polar",
      polar_subscription_id: subId,
      polar_product_id: a.productId,
      polar_status: status,
      issued_via: "subscription.created",
      ...(a.selfDescription ? { self_description: a.selfDescription } : {}),
    },
    is_lifetime: false,
    deal_seq: null,
    updated_at: now,
  };
  await upsertLicense(env.DB, lic);
  return {
    ok: true,
    action: "issued",
    license_key: lic.key,
    message: `new ${plan} license issued for ${a.email} (polar)`,
  };
}

async function onSubscriptionUpdated(
  env: PolarEnv,
  a: { email: string; productId?: string; data: Record<string, unknown> },
): Promise<HandlerResult> {
  if (!a.email) return { ok: false, action: "error", message: "missing email" };
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) {
    return await onSubscriptionActive(env, {
      email: a.email,
      productId: a.productId,
      data: a.data,
    });
  }
  const newPlan = a.productId ? readProductMap(env).get(a.productId) : undefined;
  if (newPlan && newPlan !== lic.plan) lic.plan = newPlan;
  const status = extractStatus(a.data);
  // Polar sub statuses: active, canceled, past_due, unpaid, incomplete, trialing
  lic.active = status === "active" || status === "trialing" || status === "past_due";
  lic.metadata = { ...lic.metadata, polar_status: status, provider: "polar" };
  await upsertLicense(env.DB, lic);
  return {
    ok: true,
    action: "updated",
    license_key: lic.key,
    message: `license updated plan=${lic.plan} active=${lic.active} (polar)`,
  };
}

async function onSubscriptionInactive(
  env: PolarEnv,
  a: { email: string; data: Record<string, unknown> },
): Promise<HandlerResult> {
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) return { ok: true, action: "noop", message: "no license to deactivate" };
  if (lic.is_lifetime) {
    return {
      ok: true,
      action: "noop",
      license_key: lic.key,
      message: "lifetime license preserved",
    };
  }
  lic.active = false;
  lic.metadata = {
    ...lic.metadata,
    polar_status: extractStatus(a.data) || "canceled",
    provider: "polar",
  };
  await upsertLicense(env.DB, lic);
  return {
    ok: true,
    action: "deactivated",
    license_key: lic.key,
    message: `license deactivated for ${a.email} (polar)`,
  };
}
