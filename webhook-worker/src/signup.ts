/**
 * Durable email-signup ingestion (POST /v1/signup).
 *
 * Called server-to-server by the Vercel landing route (app/api/notify).
 * Auth: shared secret via `x-signup-key` — this endpoint must not be
 * callable by arbitrary clients, both to keep the table clean and because
 * it would otherwise be a free email-storage oracle.
 *
 * The row in D1 is the source of truth. The landing route only reports
 * success to the visitor after this endpoint has confirmed the write.
 *
 * Privacy: full email addresses never go to console — logs carry a short
 * SHA-256 prefix instead.
 */

export interface SignupEnv {
  DB: D1Database;
  SIGNUP_SHARED_SECRET?: string;
}

export const ALLOWED_ROLES = new Set([
  "analyst",
  "journalist",
  "developer",
  "rotator",
  "diaspora",
  "other",
]);

const MAX_EMAIL_LENGTH = 254;
const MAX_LOCAL_LENGTH = 64;
// Pragmatic RFC-5322-adjacent shape: one @, non-empty local, dotted domain
// with a 2+ char TLD, no whitespace. Deliberately not a full RFC grammar.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Trim + lower-case. Returns null when the input is not a plausible address. */
export function normalizeEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase();
  if (!email || email.length > MAX_EMAIL_LENGTH) return null;
  const at = email.indexOf("@");
  if (at <= 0 || at > MAX_LOCAL_LENGTH) return null;
  if (!EMAIL_RE.test(email)) return null;
  return email;
}

/**
 * "" (role field left on the placeholder) is valid and maps to "unknown";
 * any other value must be in the known set.
 */
export function normalizeRole(raw: unknown): string | null {
  if (raw === undefined || raw === null) return "unknown";
  if (typeof raw !== "string") return null;
  const role = raw.trim().toLowerCase();
  if (role === "") return "unknown";
  return ALLOWED_ROLES.has(role) ? role : null;
}

export async function emailLogRef(email: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email));
  return [...new Uint8Array(digest)]
    .slice(0, 6)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

interface SignupBody {
  email?: unknown;
  role?: unknown;
  source?: unknown;
  consent?: unknown;
  consent_version?: unknown;
}

export async function handleSignup(request: Request, env: SignupEnv): Promise<Response> {
  const secret = (env.SIGNUP_SHARED_SECRET ?? "").trim();
  if (!secret) {
    console.error("[signup] SIGNUP_SHARED_SECRET not set");
    return json({ ok: false, error: "server not configured" }, 500);
  }
  const provided = request.headers.get("x-signup-key") ?? "";
  if (!timingSafeEqual(provided, secret)) {
    return json({ ok: false, error: "forbidden" }, 403);
  }

  let body: SignupBody;
  try {
    body = (await request.json()) as SignupBody;
  } catch {
    return json({ ok: false, error: "invalid json" }, 400);
  }

  const email = normalizeEmail(body.email);
  if (!email) return json({ ok: false, error: "invalid email" }, 400);

  const role = normalizeRole(body.role);
  if (role === null) return json({ ok: false, error: "invalid role" }, 400);

  if (body.consent !== true) return json({ ok: false, error: "consent required" }, 400);

  const source =
    typeof body.source === "string" && body.source.trim()
      ? body.source.trim().slice(0, 120)
      : "unknown";
  const consentVersion =
    typeof body.consent_version === "string" && body.consent_version.trim()
      ? body.consent_version.trim().slice(0, 40)
      : null;
  const now = new Date().toISOString();

  const ref = await emailLogRef(email);
  try {
    const existing = await env.DB.prepare("SELECT id FROM waitlist WHERE email = ?1")
      .bind(email)
      .first<{ id: number }>();

    if (existing) {
      // Duplicate submission is idempotent: refresh role/updated_at, keep the
      // original consent + created_at record.
      await env.DB.prepare("UPDATE waitlist SET role = ?1, updated_at = ?2 WHERE email = ?3")
        .bind(role, now, email)
        .run();
      console.log(`[signup] duplicate ok ref=${ref} role=${role}`);
      return json({ ok: true, duplicate: true });
    }

    await env.DB.prepare(
      "INSERT INTO waitlist (email, role, source, consent_at, consent_version, created_at, updated_at) " +
        "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)",
    )
      .bind(email, role, source, now, consentVersion, now)
      .run();
    console.log(`[signup] stored ref=${ref} role=${role} source=${source}`);
    return json({ ok: true, duplicate: false });
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    console.error(`[signup] D1 write FAILED ref=${ref}: ${message}`);
    return json({ ok: false, error: "storage failure" }, 500);
  }
}

/** Constant-time-ish string comparison for the shared secret. */
function timingSafeEqual(a: string, b: string): boolean {
  const enc = new TextEncoder();
  const ab = enc.encode(a);
  const bb = enc.encode(b);
  if (ab.length !== bb.length) return false;
  let diff = 0;
  for (let i = 0; i < ab.length; i++) diff |= ab[i] ^ bb[i];
  return diff === 0;
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
