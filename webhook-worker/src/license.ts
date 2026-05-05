/**
 * D1-backed license store. Mirrors koreanpulse.license_postgres.PostgresLicenseStore
 * but in TypeScript over Cloudflare D1 (SQLite).
 *
 * Pricing v2 (2026-05-05) — workflow-priced 3-tier ladder:
 *   solo    — $29/mo, 2K queries, 5 watchlists, 30d archive, 1 alert channel
 *   analyst — $79/mo, 15K queries, 25 watchlists, 1y archive, 3 alert channels
 *   desk    — $249/mo, 100K queries, 100 watchlists, 1y archive, 5 alert channels, 3 seats
 *
 * Free Public Web (`/today`) is unauthenticated — no license object exists
 * for it. Deprecated plans (free / starter / indie / pro / enterprise)
 * remain in the CHECK constraint for back-compat with historical rows.
 *
 * Design Partner Lifetime ($299, 20 seats) maps to `analyst` plan with
 * `is_lifetime = 1`.
 */

import type { D1Database } from "@cloudflare/workers-types";

export type Plan =
  | "solo"
  | "analyst"
  | "desk"
  // Deprecated aliases — historical license rows / webhook payloads.
  | "free"
  | "starter"
  | "indie"
  | "pro"
  | "enterprise";

export interface License {
  key: string;
  plan: Plan;
  customer_email: string;
  active: boolean;
  created_at: string;
  period_calls: number;
  period_started_at: string;
  metadata: Record<string, unknown>;
  is_lifetime: boolean;
  deal_seq: number | null;
  updated_at: string;
}

export interface LicenseCheckResult {
  ok: boolean;
  code?: "missing" | "invalid" | "inactive" | "quota_exceeded";
  reason?: string;
  plan?: Plan;
  period_calls?: number;
}

/**
 * Plan call limit (soft, per month). -1 = unlimited.
 * Active tiers: solo / analyst / desk. Deprecated aliases mirror Solo
 * limits so historical rows resolve sensibly.
 */
export const PLAN_CALLS_PER_MONTH: Record<Plan, number> = {
  solo: 2_000,
  analyst: 15_000,
  desk: 100_000,
  // Deprecated — back-compat aliases.
  free: 2_000,
  starter: 2_000,
  indie: 2_000,
  pro: 2_000,
  enterprise: 2_000,
};

interface LicenseRow {
  key: string;
  plan: string;
  customer_email: string;
  active: number;
  created_at: string;
  period_calls: number;
  period_started_at: string;
  metadata: string;
  is_lifetime: number;
  deal_seq: number | null;
  updated_at: string;
}

function rowToLicense(row: LicenseRow): License {
  let meta: Record<string, unknown> = {};
  try {
    meta = JSON.parse(row.metadata || "{}");
  } catch {
    meta = {};
  }
  return {
    key: row.key,
    plan: row.plan as Plan,
    customer_email: row.customer_email,
    active: row.active === 1,
    created_at: row.created_at,
    period_calls: row.period_calls,
    period_started_at: row.period_started_at,
    metadata: meta,
    is_lifetime: row.is_lifetime === 1,
    deal_seq: row.deal_seq,
    updated_at: row.updated_at,
  };
}

export async function getByKey(db: D1Database, key: string): Promise<License | null> {
  const row = await db
    .prepare("SELECT * FROM licenses WHERE key = ?")
    .bind(key)
    .first<LicenseRow>();
  return row ? rowToLicense(row) : null;
}

export async function findByEmail(db: D1Database, email: string): Promise<License | null> {
  // Returns most recently created. Case-insensitive match (LOWER(email)).
  const row = await db
    .prepare(
      `SELECT * FROM licenses
        WHERE LOWER(customer_email) = LOWER(?)
        ORDER BY created_at DESC
        LIMIT 1`,
    )
    .bind(email)
    .first<LicenseRow>();
  return row ? rowToLicense(row) : null;
}

export async function nextLifetimeSeq(db: D1Database): Promise<number> {
  const row = await db
    .prepare(
      `SELECT COALESCE(MAX(deal_seq), 0) AS max_seq
         FROM licenses
        WHERE is_lifetime = 1`,
    )
    .first<{ max_seq: number }>();
  return (row?.max_seq ?? 0) + 1;
}

export async function upsertLicense(db: D1Database, lic: License): Promise<void> {
  const metaJson = JSON.stringify(lic.metadata);
  const isLifetime = lic.is_lifetime ? 1 : 0;
  const dealSeq = lic.deal_seq;
  await db
    .prepare(
      `INSERT INTO licenses (
          key, plan, customer_email, active, created_at,
          period_calls, period_started_at, metadata,
          is_lifetime, deal_seq, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          plan              = excluded.plan,
          customer_email    = excluded.customer_email,
          active            = excluded.active,
          period_calls      = excluded.period_calls,
          period_started_at = excluded.period_started_at,
          metadata          = excluded.metadata,
          is_lifetime       = excluded.is_lifetime,
          deal_seq          = excluded.deal_seq,
          updated_at        = excluded.updated_at`,
    )
    .bind(
      lic.key,
      lic.plan,
      lic.customer_email,
      lic.active ? 1 : 0,
      lic.created_at,
      lic.period_calls,
      lic.period_started_at,
      metaJson,
      isLifetime,
      dealSeq,
      new Date().toISOString(),
    )
    .run();
}

/**
 * Atomic counter bump. Returns the new period_calls value.
 * Throws if the key is unknown.
 */
export async function incrementUsage(
  db: D1Database,
  key: string,
  n: number = 1,
): Promise<number> {
  const result = await db
    .prepare(
      `UPDATE licenses
          SET period_calls = period_calls + ?,
              updated_at = ?
        WHERE key = ?
       RETURNING period_calls`,
    )
    .bind(n, new Date().toISOString(), key)
    .first<{ period_calls: number }>();
  if (!result) {
    throw new Error(`license key not found: ${key.slice(0, 8)}…`);
  }
  return result.period_calls;
}

/**
 * Validate + charge in one call. Mirrors the Python
 * `validate_license_or_raise` semantics but returns a result object
 * instead of raising — Worker handlers don't throw across boundaries.
 */
export async function validateAndCharge(
  db: D1Database,
  licenseKey: string | null | undefined,
  costUnits: number = 1,
): Promise<LicenseCheckResult> {
  if (!licenseKey || !licenseKey.trim()) {
    return { ok: false, code: "missing", reason: "missing license key" };
  }
  const lic = await getByKey(db, licenseKey.trim());
  if (!lic) {
    return { ok: false, code: "invalid", reason: "invalid license key" };
  }
  if (!lic.active) {
    return {
      ok: false,
      code: "inactive",
      reason: `license inactive (plan=${lic.plan})`,
    };
  }
  const monthly = PLAN_CALLS_PER_MONTH[lic.plan];
  if (monthly !== -1 && lic.period_calls + costUnits > monthly) {
    return {
      ok: false,
      code: "quota_exceeded",
      reason: `quota exceeded for plan=${lic.plan} (${lic.period_calls}/${monthly})`,
    };
  }
  const newTotal = await incrementUsage(db, lic.key, costUnits);
  return {
    ok: true,
    plan: lic.plan,
    period_calls: newTotal,
  };
}

/**
 * Idempotency check — returns true if this webhook_id is new (first
 * time we've seen it). Insert is atomic; concurrent dupes lose the
 * insert race and return false.
 */
export async function markEventSeen(
  db: D1Database,
  webhookId: string,
  eventName: string,
  result: { license_key?: string; action?: string; note?: string } = {},
): Promise<boolean> {
  if (!webhookId) return true; // no idempotency key — treat as new
  try {
    await db
      .prepare(
        `INSERT INTO webhook_events (webhook_id, event_name, license_key, action, note)
         VALUES (?, ?, ?, ?, ?)`,
      )
      .bind(
        webhookId,
        eventName,
        result.license_key ?? null,
        result.action ?? null,
        result.note ?? null,
      )
      .run();
    return true;
  } catch (exc) {
    // UNIQUE constraint failure = duplicate. Any other error: rethrow so
    // the handler returns 500 and LS retries.
    const message = exc instanceof Error ? exc.message : String(exc);
    if (message.includes("UNIQUE") || message.includes("duplicate")) {
      return false;
    }
    throw exc;
  }
}

/**
 * Generate a fresh license key. 32 bytes of randomness, urlsafe-base64,
 * `kp_` prefix to match the Python issuer.
 */
export function issueLicenseKey(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  // Convert to URL-safe base64 without padding (matches Python's
  // secrets.token_urlsafe(32)).
  const b64 = btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
  return `kp_${b64}`;
}
