/**
 * License-key delivery email — sent on subscription.created (Polar).
 *
 * Provider: Resend (https://resend.com). Single REST POST, no SDK.
 *
 * Behaviour when RESEND_API_KEY or RESEND_FROM is unset:
 *   - Silently skip (no throw, log a warning to console).
 *   - License row is still upserted in D1 — operator can deliver the key
 *     manually from the dashboard until the secret lands.
 *   - This keeps webhook idempotency clean (Polar retries see the same
 *     license_key whether or not the email went out).
 */

export interface EmailEnv {
  RESEND_API_KEY?: string;
  RESEND_FROM?: string;     // e.g. "Koreanpulse <license@koreanpulse.dev>"
  RESEND_REPLY_TO?: string; // e.g. "support@koreanpulse.dev"
}

export interface LicenseEmailPayload {
  to: string;
  license_key: string;
  // Active tiers are solo / analyst / desk. Deprecated aliases (free /
  // starter / indie / pro / enterprise) shouldn't reach this email path
  // — Polar only issues solo/analyst/desk — but we accept the wider
  // string to stay aligned with the upstream Plan type without forcing
  // a type assertion at every call site.
  plan: string;
  is_lifetime?: boolean;
}

const PLAN_PRICE: Record<string, string> = {
  solo: "$29/mo",
  analyst: "$79/mo",
  desk: "$249/mo",
};

const PLAN_QUOTA: Record<string, string> = {
  solo: "2,000 queries/mo",
  analyst: "15,000 queries/mo",
  desk: "100,000 queries/mo",
};

function buildBody(p: LicenseEmailPayload): string {
  const planLabel = p.is_lifetime
    ? `${p.plan} (Lifetime — Design Partner)`
    : `${p.plan} (${PLAN_PRICE[p.plan] ?? "—"})`;
  const quota = PLAN_QUOTA[p.plan] ?? "see /pricing";

  return `Hi,

Thanks for subscribing to Koreanpulse — Korean industry intelligence MCP
for foreign fund analysts.

Your license key (${planLabel}):

    ${p.license_key}

Keep this key private. It unlocks the two paid MCP tools:

  • monitor_activist_investors — Korean activist filer match
    (KCGI, Align Partners, Truston, Anda, Cha, VIP, Life, Platform,
    ValueAct, Elliott)

  • monitor_foreign_holders — global allowlist
    (BlackRock, Vanguard, Norges, GIC, Temasek, State Street, Fidelity,
    Capital Group, T. Rowe Price, Wellington, Goldman, JPMorgan,
    Morgan Stanley, Citadel, Millennium, Bridgewater + others)

The 5 free tools (track_korean_filings, lookup_corp_code,
resolve_stock_code, search_korean_industry_news, koreanpulse_about)
keep working without a key.

──── How to use the key ────

1) ChatGPT / Claude.ai (hosted, no install)

   Add https://mcp.koreanpulse.dev/mcp as a custom connector once.
   When asking a paid-tool question, include the key in your prompt:

     "Run monitor_activist_investors on Samsung Electronics with
      license_key=${p.license_key.slice(0, 12)}…"

2) Claude Desktop / Cursor (stdio install)

   pip install koreanpulse, then add to claude_desktop_config.json:

     "koreanpulse": {
       "command": "koreanpulse",
       "env": {
         "KOREANPULSE_LICENSE_KEY": "${p.license_key}",
         "DART_API_KEY":   "<your DART API key>",
         "OPENAI_API_KEY": "<your OpenAI API key, only if KOREANPULSE_CACHE_MODE=local>"
       }
     }

3) OpenAI Responses API (developer)

     client.responses.create(
       model="gpt-5",
       tools=[{"type": "mcp", "server_url": "https://mcp.koreanpulse.dev/mcp"}],
       input="... license_key=${p.license_key.slice(0, 12)}… ..."
     )

──── Quota ────

  ${planLabel}:  ${quota}

──── Q3 2026 ship targets ────

Watchlist polling + Discord/Telegram/Slack alert dispatch + per-tier
seat enforcement. Until then queries are the only runtime-enforced
limit; watchlist counts and alert-channel limits are paper limits and
won't trigger billing changes.

──── Disclaimer ────

Koreanpulse is a read-only data layer. Not investment advice. Korea
Capital Markets Act §101 self-classified. See:
  https://koreanpulse.dev/terms
  https://koreanpulse.dev/privacy

Reply to this email if you need help.

— Koreanpulse
  https://koreanpulse.dev
`;
}

export async function sendLicenseEmail(
  env: EmailEnv,
  payload: LicenseEmailPayload,
): Promise<{ ok: boolean; skipped?: boolean; error?: string; id?: string }> {
  const apiKey = (env.RESEND_API_KEY ?? "").trim();
  const from = (env.RESEND_FROM ?? "").trim();
  if (!apiKey || !from) {
    console.warn(
      `[email] RESEND_API_KEY or RESEND_FROM not configured — skipping license email to ${payload.to} (license=${payload.license_key.slice(0, 12)}…)`,
    );
    return { ok: false, skipped: true };
  }
  if (!payload.to || !payload.to.includes("@")) {
    console.warn(`[email] invalid recipient "${payload.to}" — skipping`);
    return { ok: false, skipped: true, error: "invalid recipient" };
  }

  const body = buildBody(payload);
  const subject = `Welcome to Koreanpulse — your ${payload.plan} license key`;
  const replyTo = (env.RESEND_REPLY_TO ?? "").trim();

  const resendBody: Record<string, unknown> = {
    from,
    to: [payload.to],
    subject,
    text: body,
  };
  if (replyTo) {
    resendBody.reply_to = replyTo;
  }

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(resendBody),
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      console.warn(
        `[email] Resend POST failed: ${res.status} ${res.statusText} body=${txt.slice(0, 200)}`,
      );
      return { ok: false, error: `${res.status} ${res.statusText}` };
    }
    const json = (await res.json().catch(() => ({}))) as { id?: string };
    console.log(
      `[email] license email sent: id=${json.id ?? "?"} to=${payload.to} plan=${payload.plan}`,
    );
    return { ok: true, id: json.id };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(`[email] Resend POST threw: ${msg}`);
    return { ok: false, error: msg };
  }
}
