/**
 * Discord webhook push — fire-and-forget. If the webhook URL is unset
 * or the call fails, the daily build still succeeds (we log and move on).
 *
 * Embed format keeps it scannable: 1 title row, 1 timestamp, up to
 * 5 activist filings + 5 top filings as fields. Discord caps embeds
 * at 25 fields and 6000 chars total — we stay well below.
 */

import type { DailySnapshot } from "./render";

const SITE = "https://koreanpulse.dev";

interface DiscordEmbed {
  title: string;
  url: string;
  description?: string;
  color: number;
  timestamp: string;
  footer?: { text: string };
  fields?: { name: string; value: string; inline?: boolean }[];
}

export async function postToDiscord(
  webhookUrl: string,
  snap: DailySnapshot,
): Promise<{ ok: boolean; status?: number; error?: string }> {
  if (!webhookUrl) {
    return { ok: false, error: "no webhook url" };
  }

  const fields: DiscordEmbed["fields"] = [];

  for (const ff of snap.foreign_flows.slice(0, 4)) {
    const corp = ff.corp_name_en || ff.corp_name_ko;
    const value = `**${ff.holder_label}** disclosed on ${corp}${ff.stock_code ? ` (${ff.stock_code})` : ""}\n[${truncate(ff.title_en || ff.title, 200)}](${ff.dart_url})`;
    fields.push({ name: `💰 ${ff.filed_at}`, value: truncate(value, 1024) });
  }

  for (const af of snap.activist_filings.slice(0, 4)) {
    const corp = af.corp_name_en || af.corp_name_ko;
    const value = `**${af.activist_label}** filed on ${corp}${af.stock_code ? ` (${af.stock_code})` : ""}\n[${truncate(af.title_en || af.title, 200)}](${af.dart_url})`;
    fields.push({ name: `🚨 ${af.filed_at}`, value: truncate(value, 1024) });
  }

  for (const f of snap.top_filings.slice(0, 4)) {
    const corp = f.corp_name_en || f.corp_name_ko;
    const value = `**${corp}**${f.stock_code ? ` (${f.stock_code})` : ""}\n[${truncate(f.title_en || f.title, 200)}](${f.dart_url})`;
    fields.push({ name: `📄 ${f.filed_at}`, value: truncate(value, 1024) });
  }

  // Description leads with the day's takeaway so the embed is scannable
  // at a glance — a Discord reader who never clicks through still gets
  // the headline. Falls back to filing counts on quiet days.
  const counts = `${snap.foreign_flows.length} foreign-holder · ${snap.activist_filings.length} activist · ${snap.top_filings.length} major filings`;
  const body = snap.takeaway.length
    ? snap.takeaway.map((b) => `› ${b}`).join("\n") + `\n\n_${counts}_`
    : counts;

  // A subscriber reading "0 activist" has no way to tell a quiet day from a
  // DART outage, and this embed is the only surface most of them ever see —
  // so a partial build has to say so before the counts, not after.
  const warning = snap.degraded?.length
    ? `⚠️ **Partial build** — DART did not return ${snap.degraded.join(
        " and ",
      )}. Counts below undercount reality.\n\n`
    : "";
  const description = warning + body;

  const embed: DiscordEmbed = {
    title: `Today on KOSPI / KOSDAQ — ${snap.date}`,
    url: `${SITE}/today`,
    description: truncate(description, 4000),
    // Amber is the brand colour and reads as "normal" here; a partial build
    // gets red so it is distinguishable in a scrolled feed without reading.
    color: snap.degraded?.length ? 0xdc2626 : 0xf0b429,
    timestamp: snap.generated_at,
    footer: { text: "koreanpulse.dev · DART · no investment advice" },
    fields,
  };

  try {
    const resp = await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: "koreanpulse",
        embeds: [embed],
      }),
    });
    return { ok: resp.ok, status: resp.status };
  } catch (exc) {
    const message = exc instanceof Error ? exc.message : String(exc);
    return { ok: false, error: message };
  }
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
