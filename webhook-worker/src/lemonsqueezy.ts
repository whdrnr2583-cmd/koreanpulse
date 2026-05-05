/**
 * Lemon Squeezy webhook handling for the simplified pricing model.
 * TypeScript port of `koreanpulse.billing.lemonsqueezy` over Cloudflare D1.
 *
 * Flow per webhook:
 *   1. HMAC-SHA256 signature verify (LS_WEBHOOK_SECRET).
 *   2. JSON parse.
 *   3. Idempotency check via D1 `webhook_events.webhook_id` PK.
 *   4. Dispatch on `meta.event_name` to per-event handler.
 *   5. Handler upserts to D1 `licenses`.
 *   6. Always return 200 — surface failure in body so the LS dashboard
 *      shows it but no retry storm.
 */

import type { D1Database } from "@cloudflare/workers-types";
import {
  findByEmail,
  getByKey,
  issueLicenseKey,
  markEventSeen,
  nextLifetimeSeq,
  upsertLicense,
  type License,
  type Plan,
} from "./license";

export interface Env {
  DB: D1Database;
  LEMONSQUEEZY_WEBHOOK_SECRET: string;
  KOREANPULSE_CACHE_SHARED_SECRET: string;
  // Active tiers (pricing v2)
  LEMONSQUEEZY_VARIANT_SOLO: string;
  LEMONSQUEEZY_VARIANT_ANALYST: string;
  LEMONSQUEEZY_VARIANT_DESK: string;
  // Lifetime: design-partner-only, 20 seats max, NOT in public pricing.
  LEMONSQUEEZY_VARIANT_LIFETIME: string;
  // Deprecated / back-compat — historical storefront rows. Empty in prod.
  LEMONSQUEEZY_VARIANT_PRO?: string;
  LEMONSQUEEZY_VARIANT_STARTER?: string;
  LEMONSQUEEZY_VARIANT_INDIE?: string;
  LEMONSQUEEZY_VARIANT_ENTERPRISE?: string;
  VALIDATE_CACHE_TTL_SECONDS?: string;
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

function readVariantMap(env: Env): Map<string, Plan> {
  const m = new Map<string, Plan>();
  const pairs: [string | undefined, Plan][] = [
    // Active 2026-05-05+ (workflow-priced 3-tier ladder)
    [env.LEMONSQUEEZY_VARIANT_SOLO, "solo"],
    [env.LEMONSQUEEZY_VARIANT_ANALYST, "analyst"],
    [env.LEMONSQUEEZY_VARIANT_DESK, "desk"],
    // Deprecated — historical storefront rows. Normally empty in production.
    [env.LEMONSQUEEZY_VARIANT_PRO, "pro"],
    [env.LEMONSQUEEZY_VARIANT_STARTER, "starter"],
    [env.LEMONSQUEEZY_VARIANT_INDIE, "indie"],
    [env.LEMONSQUEEZY_VARIANT_ENTERPRISE, "enterprise"],
  ];
  for (const [vid, plan] of pairs) {
    const trimmed = (vid ?? "").trim();
    if (trimmed) m.set(trimmed, plan);
  }
  return m;
}

// ── Signature verification (HMAC-SHA256, constant-time compare) ────────────

export async function verifyLsSignature(
  body: string,
  signatureHeader: string,
  secret: string,
): Promise<boolean> {
  if (!signatureHeader || !secret) return false;
  const expected = await hmacSha256Hex(secret, body);
  return constantTimeEq(expected, signatureHeader.trim());
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

// ── Field extractors ───────────────────────────────────────────────────────

function extractEmail(attrs: Record<string, unknown>): string {
  const v = (attrs.user_email ?? attrs.email ?? attrs.customer_email ?? "") as string;
  return String(v).trim().toLowerCase();
}

function extractVariantId(attrs: Record<string, unknown>): string | undefined {
  if ("variant_id" in attrs) return String(attrs.variant_id);
  const first = (attrs.first_order_item ?? {}) as Record<string, unknown>;
  if (first && typeof first === "object" && "variant_id" in first) {
    return String(first.variant_id);
  }
  return undefined;
}

function extractSelfDescription(
  payload: Record<string, unknown>,
  attrs: Record<string, unknown>,
): string | undefined {
  const candidates: unknown[] = [];

  const meta = (payload.meta ?? {}) as Record<string, unknown>;
  const cd = (meta.custom_data ?? {}) as Record<string, unknown>;
  if (cd && typeof cd === "object") candidates.push((cd as Record<string, unknown>).role);

  const first = (attrs.first_order_item ?? {}) as Record<string, unknown>;
  if (first && typeof first === "object") {
    const po = (first.product_options ?? {}) as Record<string, unknown>;
    if (po && typeof po === "object") {
      const custom = (po.custom ?? {}) as Record<string, unknown>;
      if (custom && typeof custom === "object") {
        candidates.push((custom as Record<string, unknown>).role);
      }
    }
  }

  const cf = (attrs.custom_fields_responses ?? {}) as Record<string, unknown>;
  if (cf && typeof cf === "object") candidates.push((cf as Record<string, unknown>).role);

  for (const c of candidates) {
    if (!c) continue;
    const s = String(c).trim().toLowerCase();
    if (!s) continue;
    return ALLOWED_ROLES.has(s) ? s : "other";
  }
  return undefined;
}

// ── Event dispatch ─────────────────────────────────────────────────────────

export async function handleEvent(env: Env, payload: any): Promise<HandlerResult> {
  const meta = (payload?.meta ?? {}) as Record<string, unknown>;
  const eventName = String(meta.event_name ?? "").trim();
  const webhookId = String(meta.webhook_id ?? "").trim();

  const data = (payload?.data ?? {}) as Record<string, unknown>;
  const attrs = (data.attributes ?? {}) as Record<string, unknown>;
  const entityId = String(data.id ?? "");
  const email = extractEmail(attrs);
  const variantId = extractVariantId(attrs);
  const selfDescription = extractSelfDescription(payload, attrs);

  // Idempotency. Note: the row gets written ONLY after the dispatch
  // succeeds (so a transient failure doesn't lose retries). We pre-check
  // here and write the audit row at the end of dispatch.
  if (webhookId) {
    const existing = await env.DB
      .prepare("SELECT 1 FROM webhook_events WHERE webhook_id = ?")
      .bind(webhookId)
      .first();
    if (existing) {
      return { ok: true, action: "duplicate_ignored", message: `already processed ${webhookId}` };
    }
  }

  let result: HandlerResult;

  switch (eventName) {
    case "subscription_created":
    case "subscription_resumed":
      result = await onSubscriptionActive(env, { email, variantId, attrs, entityId, selfDescription });
      break;
    case "subscription_updated":
      result = await onSubscriptionUpdated(env, { email, variantId, attrs });
      break;
    case "subscription_cancelled":
    case "subscription_expired":
      result = await onSubscriptionInactive(env, { email, attrs });
      break;
    case "subscription_payment_success":
      result = await onPaymentSuccess(env, { email });
      break;
    case "subscription_payment_failed":
      result = await onPaymentFailed(env, { email });
      break;
    case "order_created":
      result = await onOrderCreated(env, { email, variantId, entityId, selfDescription });
      break;
    default:
      result = { ok: true, action: "ignored", message: `no handler for event_name=${eventName}` };
  }

  // Persist idempotency log AFTER dispatch finishes — only successful
  // events are recorded so retries can re-attempt failed ones.
  if (webhookId && result.ok) {
    await markEventSeen(env.DB, webhookId, eventName, {
      license_key: result.license_key,
      action: result.action,
      note: result.message,
    });
  }

  return result;
}

// ── Per-event handlers ─────────────────────────────────────────────────────

interface SubArgs {
  email: string;
  variantId?: string;
  attrs: Record<string, unknown>;
  entityId: string;
  selfDescription?: string;
}

async function onSubscriptionActive(env: Env, a: SubArgs): Promise<HandlerResult> {
  if (!a.email) return { ok: false, action: "error", message: "missing email" };
  const plan = readVariantMap(env).get(a.variantId ?? "");
  if (!plan) {
    return {
      ok: false, action: "error",
      message: `unknown variant_id=${a.variantId}; configure LEMONSQUEEZY_VARIANT_*`,
    };
  }

  const existing = await findByEmail(env.DB, a.email);
  const status = String(a.attrs.status ?? "");
  const subId = a.entityId;

  if (existing) {
    existing.plan = plan;
    existing.active = true;
    existing.metadata = {
      ...existing.metadata,
      ls_subscription_id: subId,
      ls_variant_id: a.variantId,
      ls_status: status,
    };
    if (a.selfDescription) {
      existing.metadata.self_description = a.selfDescription;
    }
    await upsertLicense(env.DB, existing);
    return {
      ok: true, action: "upgraded", license_key: existing.key,
      message: `existing license upgraded to ${plan}`,
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
      ls_subscription_id: subId,
      ls_variant_id: a.variantId,
      ls_status: status,
      issued_via: "subscription_created",
      ...(a.selfDescription ? { self_description: a.selfDescription } : {}),
    },
    is_lifetime: false,
    deal_seq: null,
    updated_at: now,
  };
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "issued", license_key: lic.key,
    message: `new ${plan} license issued for ${a.email}`,
  };
}

async function onSubscriptionUpdated(
  env: Env,
  a: { email: string; variantId?: string; attrs: Record<string, unknown> },
): Promise<HandlerResult> {
  if (!a.email) return { ok: false, action: "error", message: "missing email" };
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) {
    // Treat as new but without entity_id (we don't have it for "updated"
    // events that arrive for never-seen subscriptions — rare).
    return await onSubscriptionActive(env, { email: a.email, variantId: a.variantId, attrs: a.attrs, entityId: "" });
  }
  const newPlan = a.variantId ? readVariantMap(env).get(a.variantId) : undefined;
  if (newPlan && newPlan !== lic.plan) lic.plan = newPlan;
  const status = String(a.attrs.status ?? "");
  lic.active = status === "active" || status === "on_trial" || status === "past_due";
  lic.metadata = { ...lic.metadata, ls_status: status };
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "updated", license_key: lic.key,
    message: `license updated plan=${lic.plan} active=${lic.active}`,
  };
}

async function onSubscriptionInactive(
  env: Env,
  a: { email: string; attrs: Record<string, unknown> },
): Promise<HandlerResult> {
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) return { ok: true, action: "noop", message: "no license to deactivate" };
  if (lic.is_lifetime) {
    return {
      ok: true, action: "noop",
      license_key: lic.key, message: "lifetime license preserved",
    };
  }
  lic.active = false;
  lic.metadata = { ...lic.metadata, ls_status: String(a.attrs.status ?? "cancelled") };
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "deactivated", license_key: lic.key,
    message: `license deactivated for ${a.email}`,
  };
}

async function onPaymentSuccess(env: Env, a: { email: string }): Promise<HandlerResult> {
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) return { ok: true, action: "noop", message: "no license to reset" };
  lic.period_calls = 0;
  lic.period_started_at = new Date().toISOString();
  lic.active = true;
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "period_reset", license_key: lic.key,
    message: "usage counter reset on renewal",
  };
}

async function onPaymentFailed(env: Env, a: { email: string }): Promise<HandlerResult> {
  const lic = await findByEmail(env.DB, a.email);
  if (!lic) return { ok: true, action: "noop" };
  lic.metadata = { ...lic.metadata, ls_last_payment_failed_at: new Date().toISOString() };
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "payment_failed_logged", license_key: lic.key,
    message: "payment failure logged; license still active during grace period",
  };
}

async function onOrderCreated(
  env: Env,
  a: { email: string; variantId?: string; entityId: string; selfDescription?: string },
): Promise<HandlerResult> {
  if (!a.email) return { ok: false, action: "error", message: "missing email" };
  const lifetimeVariant = (env.LEMONSQUEEZY_VARIANT_LIFETIME ?? "").trim();
  if (!lifetimeVariant || a.variantId !== lifetimeVariant) {
    return {
      ok: true, action: "ignored",
      message: `order_created variant=${a.variantId} is not the lifetime SKU`,
    };
  }

  const existing = await findByEmail(env.DB, a.email);
  if (existing && existing.is_lifetime) {
    return {
      ok: true, action: "duplicate_lifetime",
      license_key: existing.key, message: "email already has lifetime license",
    };
  }

  const dealSeq = await nextLifetimeSeq(env.DB);
  const now = new Date().toISOString();
  const lic: License = {
    key: issueLicenseKey(),
    plan: "analyst",  // pricing v2: design-partner lifetime grants Analyst forever
    customer_email: a.email,
    active: true,
    created_at: now,
    period_calls: 0,
    period_started_at: now,
    metadata: {
      lifetime: true,
      deal_seq: dealSeq,
      deal_price_usd: 299,
      ls_order_id: a.entityId,
      ls_variant_id: a.variantId,
      issued_via: "order_created",
      ...(a.selfDescription ? { self_description: a.selfDescription } : {}),
    },
    is_lifetime: true,
    deal_seq: dealSeq,
    updated_at: now,
  };
  await upsertLicense(env.DB, lic);
  return {
    ok: true, action: "lifetime_issued", license_key: lic.key,
    message: `lifetime deal #${dealSeq} issued to ${a.email}`,
  };
}

// Re-export for getByKey usage from index
export { getByKey };
