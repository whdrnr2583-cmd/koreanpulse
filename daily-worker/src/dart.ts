/**
 * DART OpenAPI client — Worker-side. Minimal port of koreanpulse.dart;
 * we only need `list.json` for the daily dashboard.
 *
 * Quota safety: DART caps each key at 40K calls/day. The daily cron runs
 * once per weekday and burns 5–10 calls (one type-D fetch + a couple of
 * type-A/B fetches). 0.025% of soft quota — no in-process counter needed.
 */

import type { Env } from "./index";
import { matchInvestor, type InvestorMatch } from "./activists";

const STATUS_OK = "000";
const STATUS_NO_RESULT = "013";

export interface DartFiling {
  corp_code: string;
  corp_name_ko: string;
  corp_name_en?: string;   // populated by translateCorpName, optional
  stock_code: string | null;
  filing_type: string;     // A/B/C/D/E/F/G/H/I/J or "?"
  title: string;
  receipt_no: string;
  filed_at: string;        // ISO date (yyyy-mm-dd)
  filer_name_ko: string | null;
  dart_url: string;
  attribution: string;
}

export interface ActivistFiling extends DartFiling {
  activist_label: string;
}

/**
 * 5%-rule filing matched against the foreign-passive-holder allowlist.
 * Used as a leading indicator of foreign capital flow into a ticker.
 */
export interface ForeignFlowFiling extends DartFiling {
  holder_label: string;     // canonical English name
  holder_origin: InvestorMatch["origin"];
}

const DART_ATTRIBUTION =
  "Source: 금융감독원 전자공시시스템 DART (https://dart.fss.or.kr/)";

interface DartListItem {
  corp_code?: string;
  corp_name?: string;
  stock_code?: string;
  rcept_no?: string;
  rcept_dt?: string;       // yyyymmdd
  report_nm?: string;
  flr_nm?: string;
}

interface DartListResponse {
  status?: string;
  message?: string;
  list?: DartListItem[];
}

function yyyymmdd(d: Date): string {
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}${mm}${dd}`;
}

function parseFiledAt(rceptDt: string): string {
  if (rceptDt && rceptDt.length === 8) {
    return `${rceptDt.slice(0, 4)}-${rceptDt.slice(4, 6)}-${rceptDt.slice(6, 8)}`;
  }
  return new Date().toISOString().slice(0, 10);
}

function parseFiling(row: DartListItem, requestedType: string | null): DartFiling {
  const receiptNo = row.rcept_no ?? "";
  const title = (row.report_nm ?? "").trim();

  return {
    corp_code: row.corp_code ?? "",
    corp_name_ko: row.corp_name ?? "",
    stock_code: row.stock_code || null,
    filing_type: requestedType ?? "?",
    title,
    receipt_no: receiptNo,
    filed_at: parseFiledAt(row.rcept_dt ?? ""),
    filer_name_ko: (row.flr_nm ?? "").trim() || null,
    dart_url: `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${receiptNo}`,
    attribution: DART_ATTRIBUTION,
  };
}

interface ListFilingsArgs {
  bgnDe: Date;
  endDe: Date;
  pblntfTy?: string;       // A/B/C/D/E/F/G/H/I/J
  pageCount?: number;      // ≤ 100
}

export async function listFilings(env: Env, args: ListFilingsArgs): Promise<DartFiling[]> {
  const params = new URLSearchParams({
    crtfc_key: env.DART_API_KEY,
    bgn_de: yyyymmdd(args.bgnDe),
    end_de: yyyymmdd(args.endDe),
    page_no: "1",
    page_count: String(Math.min(args.pageCount ?? 100, 100)),
  });
  if (args.pblntfTy) {
    params.set("pblntf_ty", args.pblntfTy);
  }

  const url = `${env.DART_API_BASE}/list.json?${params.toString()}`;
  // DART rejects calls with no User-Agent (or Cloudflare-Workers default UA)
  // by 302-redirecting to /error1.html. Sending an explicit UA + Accept
  // gets the JSON response that direct curl users see.
  const resp = await fetch(url, {
    headers: {
      "User-Agent": "koreanpulse/0.1 (+https://koreanpulse.dev)",
      Accept: "application/json,text/plain,*/*",
    },
    redirect: "manual",
  });
  if (resp.status >= 300 && resp.status < 400) {
    throw new Error(
      `DART redirected (status ${resp.status}) — likely an auth or UA-block ` +
      `issue. Verify DART_API_KEY is active.`,
    );
  }
  if (!resp.ok) {
    throw new Error(`DART HTTP ${resp.status}`);
  }
  const data = (await resp.json()) as DartListResponse;
  const status = data.status ?? "?";
  if (status === STATUS_NO_RESULT) return [];
  if (status !== STATUS_OK) {
    throw new Error(`DART ${status}: ${data.message ?? "unknown"}`);
  }

  return (data.list ?? []).map((row) => parseFiling(row, args.pblntfTy ?? null));
}

/**
 * Pull recent type-D shareholding filings, classify filers against the
 * combined allowlist (activists + foreign passive holders), and split
 * into two streams. One DART API call services both streams.
 *
 * Returns:
 *   activists       — funds known for governance pressure (KCGI, Align,
 *                     ValueAct, Elliott, etc.)
 *   foreign_flows   — large foreign passive holders (BlackRock, Vanguard,
 *                     SWFs). Their filings are a leading indicator of
 *                     foreign capital movement into a Korean ticker.
 */
export async function fetchClassifiedFilings(
  env: Env,
  daysBack: number,
): Promise<{ activists: ActivistFiling[]; foreign_flows: ForeignFlowFiling[] }> {
  const endDe = new Date();
  const bgnDe = new Date(endDe.getTime() - daysBack * 86400 * 1000);
  const filings = await listFilings(env, {
    bgnDe,
    endDe,
    pblntfTy: "D",
    pageCount: 100,
  });

  const activists: ActivistFiling[] = [];
  const foreign: ForeignFlowFiling[] = [];

  for (const f of filings) {
    const match = matchInvestor(f.filer_name_ko);
    if (!match) continue;
    if (match.klass === "activist") {
      activists.push({ ...f, activist_label: match.canonical });
    } else {
      foreign.push({
        ...f,
        holder_label: match.canonical,
        holder_origin: match.origin,
      });
    }
  }

  const desc = (a: DartFiling, b: DartFiling) => (a.filed_at < b.filed_at ? 1 : -1);
  activists.sort(desc);
  foreign.sort(desc);

  return { activists, foreign_flows: foreign };
}

// Backwards-compatible alias used during the W1 d6 transition.
export async function fetchActivistFilings(
  env: Env,
  daysBack: number,
): Promise<ActivistFiling[]> {
  const { activists } = await fetchClassifiedFilings(env, daysBack);
  return activists;
}

/**
 * Pull recent major-event (type-B) and periodic (type-A) filings — the
 * "what big companies actually said today" feed. Returns the latest N.
 */
export async function fetchTopFilings(
  env: Env,
  daysBack: number,
  limit: number,
): Promise<DartFiling[]> {
  const endDe = new Date();
  const bgnDe = new Date(endDe.getTime() - daysBack * 86400 * 1000);

  const [typeA, typeB] = await Promise.all([
    listFilings(env, { bgnDe, endDe, pblntfTy: "A", pageCount: 50 }),
    listFilings(env, { bgnDe, endDe, pblntfTy: "B", pageCount: 50 }),
  ]);

  const merged = [...typeA, ...typeB];
  merged.sort((a, b) => (a.filed_at < b.filed_at ? 1 : -1));
  return merged.slice(0, limit);
}
