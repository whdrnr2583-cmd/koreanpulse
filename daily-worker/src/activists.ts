/**
 * Investor allowlist — TS port of koreanpulse.activists, extended with
 * passive foreign institutions. Two separate label classes:
 *
 *   - "activist"  — funds known for governance pressure / 5%-rule plays
 *   - "foreign"   — large passive holders (BlackRock / Vanguard etc.).
 *                   Their 5%-rule filings signal foreign capital flow,
 *                   not activism.
 *
 * Keep KOREAN_ACTIVISTS in sync with src/koreanpulse/activists.py.
 *
 * Matching mirrors match_investor() in activists.py: names are NFKC-folded
 * and lowercased; Korean aliases match as substrings of the name with all
 * spaces/punctuation removed; Latin aliases must start on a word boundary
 * (so "Miranda Asset" is not "Anda Asset") over the punctuation-collapsed
 * name. A mixed string like "KCGI 자산운용" matches both layers.
 */

export type InvestorClass = "activist" | "foreign";

interface InvestorRecord {
  canonical: string;     // English label we surface to readers
  klass: InvestorClass;
  origin: "kr" | "us" | "uk" | "eu" | "other";
  aliasesKo: string[];   // Korean substrings (matched as-is)
  aliasesEn: string[];   // Latin substrings (matched lowercase)
}

export const KOREAN_ACTIVISTS: InvestorRecord[] = [
  { canonical: "KCGI", klass: "activist", origin: "kr", aliasesKo: ["KCGI", "케이씨지아이", "강성부펀드"], aliasesEn: ["kcgi"] },
  { canonical: "Align Partners", klass: "activist", origin: "kr", aliasesKo: ["얼라인파트너스", "얼라인 파트너스"], aliasesEn: ["align partners", "alignpartners"] },
  { canonical: "Anda Asset", klass: "activist", origin: "kr", aliasesKo: ["안다자산운용", "안다 자산운용"], aliasesEn: ["anda asset"] },
  { canonical: "Cha Partners", klass: "activist", origin: "kr", aliasesKo: ["차파트너스", "차파트너스자산운용", "차 파트너스"], aliasesEn: ["cha partners"] },
  { canonical: "Truston Asset", klass: "activist", origin: "kr", aliasesKo: ["트러스톤자산운용", "트러스톤 자산운용"], aliasesEn: ["truston asset"] },
  { canonical: "Life Asset", klass: "activist", origin: "kr", aliasesKo: ["라이프자산운용", "라이프 자산운용"], aliasesEn: ["life asset"] },
  { canonical: "Platform Partners", klass: "activist", origin: "kr", aliasesKo: ["플랫폼파트너스", "플랫폼 파트너스"], aliasesEn: ["platform partners"] },
  { canonical: "VIP Asset Management", klass: "activist", origin: "kr", aliasesKo: ["VIP자산운용", "VIP 자산운용", "브이아이피자산운용"], aliasesEn: ["vip asset"] },
  { canonical: "ValueAct Capital", klass: "activist", origin: "us", aliasesKo: ["밸류액트", "ValueAct"], aliasesEn: ["valueact"] },
  { canonical: "Elliott Management", klass: "activist", origin: "us", aliasesKo: ["엘리엇", "Elliott"], aliasesEn: ["elliott"] },
  // Added 2026-07-08 — kept in sync with src/koreanpulse/activists.py.
  // See that file for per-entry news citations.
  { canonical: "Must Asset Management", klass: "activist", origin: "kr", aliasesKo: ["머스트자산운용", "머스트 자산운용"], aliasesEn: ["must asset management", "must asset"] },
  { canonical: "Dalton Investments", klass: "activist", origin: "us", aliasesKo: ["달튼인베스트먼트", "달튼인베스트먼트코리아", "달튼 인베스트먼트"], aliasesEn: ["dalton investments"] },
  { canonical: "Flashlight Capital Partners", klass: "activist", origin: "other", aliasesKo: ["플래시라이트캐피탈파트너스", "플래시라이트캐피탈"], aliasesEn: ["flashlight capital"] },
  { canonical: "Oasis Management", klass: "activist", origin: "other", aliasesKo: ["오아시스매니지먼트", "오아시스 매니지먼트"], aliasesEn: ["oasis management"] },
  { canonical: "Palliser Capital", klass: "activist", origin: "uk", aliasesKo: ["팰리서캐피탈", "팰리서 캐피탈"], aliasesEn: ["palliser capital"] },
  { canonical: "Whitebox Advisors", klass: "activist", origin: "us", aliasesKo: ["화이트박스", "화이트박스어드바이저스"], aliasesEn: ["whitebox advisors"] },
  { canonical: "City of London Investment Management", klass: "activist", origin: "uk", aliasesKo: ["시티오브런던"], aliasesEn: ["city of london investment"] },
];

/**
 * Foreign passive institutional holders. 5%-rule filings from these
 * names indicate foreign capital flow into KOSPI/KOSDAQ tickers — the
 * leading indicator of "foreign money is showing up in this stock."
 *
 * Source: top-30 global asset managers + sovereign wealth funds known
 * to file Korean 5%-rule disclosures. List will go stale; refresh
 * quarterly by scanning recent type-D filer names.
 */
export const FOREIGN_HOLDERS: InvestorRecord[] = [
  { canonical: "BlackRock", klass: "foreign", origin: "us", aliasesKo: ["블랙록"], aliasesEn: ["blackrock"] },
  { canonical: "Vanguard", klass: "foreign", origin: "us", aliasesKo: ["뱅가드"], aliasesEn: ["vanguard"] },
  { canonical: "State Street", klass: "foreign", origin: "us", aliasesKo: ["스테이트 스트리트", "스테이트스트리트"], aliasesEn: ["state street"] },
  { canonical: "Fidelity", klass: "foreign", origin: "us", aliasesKo: ["피델리티", "에프엠알"], aliasesEn: ["fidelity", "fmr llc"] },
  { canonical: "Capital Group", klass: "foreign", origin: "us", aliasesKo: ["캐피털그룹", "캐피탈그룹"], aliasesEn: ["capital group", "capital research", "capital international investors", "capital world investors"] },
  { canonical: "T. Rowe Price", klass: "foreign", origin: "us", aliasesKo: ["티로프라이스", "티 로 프라이스"], aliasesEn: ["t. rowe price", "t rowe price"] },
  { canonical: "Wellington Management", klass: "foreign", origin: "us", aliasesKo: ["웰링턴"], aliasesEn: ["wellington"] },
  { canonical: "Matthews Asia", klass: "foreign", origin: "us", aliasesKo: ["매튜스아시아"], aliasesEn: ["matthews asia", "matthews international capital"] },
  { canonical: "Templeton", klass: "foreign", origin: "us", aliasesKo: ["템플턴"], aliasesEn: ["templeton", "franklin templeton"] },
  { canonical: "Aberdeen", klass: "foreign", origin: "uk", aliasesKo: ["애버딘", "아버딘"], aliasesEn: ["aberdeen", "abrdn"] },
  { canonical: "Schroders", klass: "foreign", origin: "uk", aliasesKo: ["슈로더"], aliasesEn: ["schroders", "schroder"] },
  { canonical: "Norges Bank (Norway SWF)", klass: "foreign", origin: "eu", aliasesKo: ["노르웨이중앙은행", "노르웨이은행"], aliasesEn: ["norges bank"] },
  { canonical: "GIC (Singapore SWF)", klass: "foreign", origin: "other", aliasesKo: ["싱가포르투자청"], aliasesEn: ["gic private", "gic pte", "government of singapore investment"] },
  { canonical: "Temasek", klass: "foreign", origin: "other", aliasesKo: ["테마섹"], aliasesEn: ["temasek"] },
  { canonical: "Goldman Sachs", klass: "foreign", origin: "us", aliasesKo: ["골드만삭스", "골드만 삭스"], aliasesEn: ["goldman sachs"] },
  { canonical: "JPMorgan", klass: "foreign", origin: "us", aliasesKo: ["JP모간", "JP모건", "제이피모건"], aliasesEn: ["jpmorgan", "jp morgan", "j p morgan"] },
  { canonical: "Morgan Stanley", klass: "foreign", origin: "us", aliasesKo: ["모건스탠리", "모건 스탠리"], aliasesEn: ["morgan stanley"] },
  { canonical: "Citadel", klass: "foreign", origin: "us", aliasesKo: ["시타델"], aliasesEn: ["citadel"] },
  { canonical: "Millennium", klass: "foreign", origin: "us", aliasesKo: ["밀레니엄"], aliasesEn: ["millennium management", "millennium international management"] },
  { canonical: "Bridgewater", klass: "foreign", origin: "us", aliasesKo: ["브리지워터"], aliasesEn: ["bridgewater"] },
];

const ALL_INVESTORS: InvestorRecord[] = [...KOREAN_ACTIVISTS, ...FOREIGN_HOLDERS];

// Mirrors _ALIAS_DENYLIST in src/koreanpulse/activists.py. Bare aliases are
// substrings, so a few collide with real, unrelated DART filers — verified
// against the corp_code registry on the Python side. Without this the daily
// dashboard reports a watch importer as a Wellington position.
const ALIAS_DENYLIST: Record<string, string[]> = {
  // "웰링턴" alone also matches the Daniel Wellington watch brand's Korean
  // subsidiary/importer naming ("다니엘웰링턴...").
  "Wellington Management": ["다니엘웰링턴", "daniel wellington"],
  // "캐피탈그룹"/"캐피털그룹" also matches "제일캐피탈그룹" and other
  // "제일캐피탈"-prefixed Korean consumer-finance entities, unrelated to
  // The Capital Group Companies.
  "Capital Group": ["제일캐피탈"],
  // Bare "밀레니엄" also matches several real, unrelated DART-registered
  // non-fund entities rather than Millennium Management: a Shilla-affiliated
  // hospitality entity, a Daedong-affiliated entity, and a holding company.
  Millennium: ["신라밀레니엄", "대동밀레니엄", "밀레니엄홀딩스"],
};

export interface InvestorMatch {
  canonical: string;
  klass: InvestorClass;
  origin: InvestorRecord["origin"];
}

const HANGUL_RE = /[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]/;

function fold(text: string): string {
  return text.normalize("NFKC").toLowerCase();
}
/** Drop everything that is not a letter/digit ("VIP 자산운용" == "(주)VIP자산운용"). */
function compact(text: string): string {
  return fold(text).replace(/[^\p{L}\p{N}]+/gu, "");
}
/** Collapse punctuation/whitespace runs to one space, keeping word boundaries. */
function spaced(text: string): string {
  return fold(text).replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}
function escapeRe(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function aliasInName(alias: string, compactName: string, spacedName: string): boolean {
  if (!alias) return false;
  if (HANGUL_RE.test(alias)) return compactName.includes(compact(alias));
  const needle = spaced(alias);
  if (!needle) return false;
  return new RegExp("(?<![a-z0-9])" + escapeRe(needle)).test(spacedName);
}

/**
 * Match a filer name against the full allowlist. Returns the matched
 * record's metadata, or null if no match.
 *
 * A record in ALIAS_DENYLIST is skipped entirely when the filer name contains
 * one of its denylisted substrings — this suppresses false positives for that
 * record only; the scan continues so unrelated entries can still match.
 */
export function matchInvestor(filerName: string | null | undefined): InvestorMatch | null {
  if (!filerName) return null;
  const name = filerName.trim();
  if (!name) return null;
  const compactName = compact(name);
  const spacedName = spaced(name);
  if (!compactName) return null;

  for (const rec of ALL_INVESTORS) {
    const denylist = ALIAS_DENYLIST[rec.canonical];
    if (denylist && denylist.some((bad) => compactName.includes(compact(bad)))) continue;
    for (const alias of [...rec.aliasesKo, ...rec.aliasesEn]) {
      if (aliasInName(alias, compactName, spacedName)) {
        return { canonical: rec.canonical, klass: rec.klass, origin: rec.origin };
      }
    }
  }
  return null;
}

/**
 * Backwards-compatible activist-only matcher. Kept so existing callers
 * (and the koreanpulse-cache Worker) don't have to change at once.
 */
export function matchActivist(filerName: string | null | undefined): string | null {
  const match = matchInvestor(filerName);
  return match && match.klass === "activist" ? match.canonical : null;
}
