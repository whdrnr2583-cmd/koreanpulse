// Email-capture endpoint with optional self-described role.
//
// Persistence (source of truth):
//   SIGNUP_INGEST_URL + SIGNUP_INGEST_SECRET → webhook-worker POST /v1/signup,
//   which stores the row durably in D1. This call is AWAITED and the visitor
//   only sees success after the write is confirmed. A failed write returns a
//   non-2xx response so the form can show a real error instead of a fake
//   "got it".
//
// Notification (secondary, best-effort):
//   SIGNUPS_WEBHOOK_URL — optional Discord/Slack ping fired only AFTER the
//   durable write succeeded. Its failure never fails the request and never
//   loses the signup.
//
// Privacy: full emails are not written to logs — a short SHA-256 prefix is
// used as the log reference.

import { NextResponse } from "next/server";

const ALLOWED_ROLES = new Set([
  "analyst",
  "journalist",
  "developer",
  "rotator",
  "diaspora",
  "other",
]);

// Version string of the privacy policy the consent checkbox references.
// Bump when app/privacy/page.tsx LAST_UPDATED changes.
const CONSENT_VERSION = "2026-05-27";

const MAX_EMAIL_LENGTH = 254;
const MAX_LOCAL_LENGTH = 64;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function normalizeEmail(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const email = raw.trim().toLowerCase();
  if (!email || email.length > MAX_EMAIL_LENGTH) return null;
  const at = email.indexOf("@");
  if (at <= 0 || at > MAX_LOCAL_LENGTH) return null;
  if (!EMAIL_RE.test(email)) return null;
  return email;
}

async function emailLogRef(email: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email));
  return Array.from(new Uint8Array(digest))
    .slice(0, 6)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function POST(req: Request) {
  let body: { email?: unknown; role?: unknown; consent?: unknown } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });
  }

  const email = normalizeEmail(body.email);
  if (!email) {
    return NextResponse.json({ ok: false, error: "invalid email" }, { status: 400 });
  }

  const rawRole = typeof body.role === "string" ? body.role.trim().toLowerCase() : "";
  if (rawRole !== "" && !ALLOWED_ROLES.has(rawRole)) {
    return NextResponse.json({ ok: false, error: "invalid role" }, { status: 400 });
  }
  const role = rawRole === "" ? "unknown" : rawRole;

  if (body.consent !== true) {
    return NextResponse.json({ ok: false, error: "consent required" }, { status: 400 });
  }

  const ingestUrl = process.env.SIGNUP_INGEST_URL;
  const ingestSecret = process.env.SIGNUP_INGEST_SECRET;
  const ref = await emailLogRef(email);

  if (!ingestUrl || !ingestSecret) {
    console.error(`[koreanpulse-notify] signup ref=${ref} REJECTED — ingest env not configured`);
    return NextResponse.json(
      { ok: false, error: "signup temporarily unavailable" },
      { status: 503 },
    );
  }

  // Durable write first — success is only reported after this confirms.
  let duplicate = false;
  try {
    const res = await fetch(ingestUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-signup-key": ingestSecret,
      },
      body: JSON.stringify({
        email,
        role,
        consent: true,
        consent_version: CONSENT_VERSION,
        source: "koreanpulse.dev/landing",
      }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) {
      console.error(
        `[koreanpulse-notify] signup ref=${ref} persistence failed: HTTP ${res.status}`,
      );
      return NextResponse.json(
        { ok: false, error: "signup temporarily unavailable" },
        { status: 502 },
      );
    }
    const data = (await res.json().catch(() => ({}))) as { duplicate?: boolean };
    duplicate = data.duplicate === true;
  } catch (err) {
    console.error(`[koreanpulse-notify] signup ref=${ref} persistence error:`, err);
    return NextResponse.json(
      { ok: false, error: "signup temporarily unavailable" },
      { status: 502 },
    );
  }

  console.log(`[koreanpulse-notify] signup stored ref=${ref} role=${role} duplicate=${duplicate}`);

  // Secondary notification — only after the durable write, never blocking,
  // and without the email address (the D1 row is the source of truth).
  const forwardUrl = process.env.SIGNUPS_WEBHOOK_URL;
  if (forwardUrl && !duplicate) {
    void fetch(forwardUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: `📥 koreanpulse signup — role: ${role} (ref ${ref})`,
        role,
        ref,
        ts: new Date().toISOString(),
        source: "koreanpulse.dev/landing",
      }),
    }).catch((err) => {
      console.warn(
        `[koreanpulse-notify] secondary notify failed (signup ref=${ref} is stored):`,
        err,
      );
    });
  }

  return NextResponse.json({ ok: true, duplicate });
}
