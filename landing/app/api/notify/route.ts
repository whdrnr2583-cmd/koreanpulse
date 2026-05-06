// Email-capture endpoint with optional self-described role.
// Captures the audience composition signal we need for BETA.md decision matrix.
//
// Persistence:
//   - SIGNUPS_WEBHOOK_URL (Vercel env): a webhook that receives every signup.
//     Set to a Discord/Slack/Telegram webhook for live ping + archive, or to
//     a Buttondown/Resend ingest URL once the list is wired. The forward is
//     fire-and-forget so a bad endpoint never blocks the user response.
//   - console.log: always emitted as a safety net in Vercel function logs.

import { NextResponse } from "next/server";

const ALLOWED_ROLES = new Set([
  "analyst",
  "journalist",
  "developer",
  "rotator",
  "diaspora",
  "other",
]);

export async function POST(req: Request) {
  let body: { email?: string; role?: string } = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });
  }

  const email = (body.email || "").trim().toLowerCase();
  if (!email || !email.includes("@")) {
    return NextResponse.json({ ok: false, error: "bad email" }, { status: 400 });
  }

  const rawRole = (body.role || "").trim().toLowerCase();
  const role = ALLOWED_ROLES.has(rawRole) ? rawRole : "unknown";
  const ts = new Date().toISOString();

  console.log(`[koreanpulse-notify] signup email=${email} role=${role} ts=${ts}`);

  const forwardUrl = process.env.SIGNUPS_WEBHOOK_URL;
  if (forwardUrl) {
    void fetch(forwardUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        // Discord/Slack-compatible field
        content: `📥 koreanpulse signup — ${email} (role: ${role})`,
        // Generic ingest payload
        email,
        role,
        ts,
        source: "koreanpulse.dev/landing",
      }),
    }).catch((err) => {
      console.warn("[koreanpulse-notify] forward failed:", err);
    });
  }

  return NextResponse.json({ ok: true });
}
