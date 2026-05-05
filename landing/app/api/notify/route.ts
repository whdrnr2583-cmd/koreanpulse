// Email-capture endpoint with optional self-described role.
// Captures the audience composition signal we need for BETA.md decision matrix.
//
// Wire to a real provider before launch:
//   - Buttondown:  POST https://api.buttondown.email/v1/subscribers
//   - ConvertKit:  POST https://api.convertkit.com/v3/forms/<id>/subscribe
//   - Lemon Squeezy: not built for this — use Buttondown
//
// For now we just log to stdout (surfaces in Vercel function log).

import { NextResponse } from "next/server";

const ALLOWED_ROLES = new Set([
  "analyst",       // foreign / boutique / hedge fund / SMB analyst covering Korea
  "journalist",    // K-content / EM journalist
  "developer",     // building tools, MCP-curious
  "rotator",       // crypto-native rotating into KRX (the original Jay persona)
  "diaspora",      // Korean-American / overseas Korean investor
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

  // Role is optional — empty / unknown values just become "unknown" so the
  // bucket exists in the analytics layer.
  const rawRole = (body.role || "").trim().toLowerCase();
  const role = ALLOWED_ROLES.has(rawRole) ? rawRole : "unknown";

  // TODO: pipe into your real provider with both email + role tags.
  console.log(`[koreanpulse-notify] signup email=${email} role=${role}`);

  // Example wiring (uncomment and set BUTTONDOWN_TOKEN env on Vercel):
  // await fetch("https://api.buttondown.email/v1/subscribers", {
  //   method: "POST",
  //   headers: {
  //     "Authorization": `Token ${process.env.BUTTONDOWN_TOKEN}`,
  //     "Content-Type": "application/json",
  //   },
  //   body: JSON.stringify({ email, tags: [`role:${role}`] }),
  // });

  return NextResponse.json({ ok: true });
}
