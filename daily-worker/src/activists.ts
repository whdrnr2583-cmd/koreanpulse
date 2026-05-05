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
 * Matching is case-insensitive substring. Korean substrings match the
 * raw filer name; latin substrings match the lowercased name. A mixed
 * string like "KCGI 자산운용" matches both layers.
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
  { canonical: "Fidelity", klass: "foreign", origin: "us", aliasesKo: ["피델리티"], aliasesEn: ["fidelity"] },
  { canonical: "Capital Group", klass: "foreign", origin: "us", aliasesKo: ["캐피털그룹", "캐피탈그룹"], aliasesEn: ["capital group", "capital research"] },
  { canonical: "T. Rowe Price", klass: "foreign", origin: "us", aliasesKo: ["티로프라이스", "티 로 프라이스"], aliasesEn: ["t. rowe price", "t rowe price"] },
  { canonical: "Wellington Management", klass: "foreign", origin: "us", aliasesKo: ["웰링턴"], aliasesEn: ["wellington"] },
  { canonical: "Matthews Asia", klass: "foreign", origin: "us", aliasesKo: ["매튜스아시아"], aliasesEn: ["matthews asia"] },
  { canonical: "Templeton", klass: "foreign", origin: "us", aliasesKo: ["템플턴"], aliasesEn: ["templeton", "franklin templeton"] },
  { canonical: "Aberdeen", klass: "foreign", origin: "uk", aliasesKo: ["애버딘", "아버딘"], aliasesEn: ["aberdeen", "abrdn"] },
  { canonical: "Schroders", klass: "foreign", origin: "uk", aliasesKo: ["슈로더"], aliasesEn: ["schroders", "schroder"] },
  { canonical: "Norges Bank (Norway SWF)", klass: "foreign", origin: "eu", aliasesKo: ["노르웨이중앙은행", "노르웨이은행"], aliasesEn: ["norges bank"] },
  { canonical: "GIC (Singapore SWF)", klass: "foreign", origin: "other", aliasesKo: ["싱가포르투자청"], aliasesEn: ["gic private", "gic pte"] },
  { canonical: "Temasek", klass: "foreign", origin: "other", aliasesKo: ["테마섹"], aliasesEn: ["temasek"] },
  { canonical: "Goldman Sachs", klass: "foreign", origin: "us", aliasesKo: ["골드만삭스", "골드만 삭스"], aliasesEn: ["goldman sachs"] },
  { canonical: "JPMorgan", klass: "foreign", origin: "us", aliasesKo: ["JP모간", "JP모건", "제이피모건"], aliasesEn: ["jpmorgan", "jp morgan"] },
  { canonical: "Morgan Stanley", klass: "foreign", origin: "us", aliasesKo: ["모건스탠리", "모건 스탠리"], aliasesEn: ["morgan stanley"] },
  { canonical: "Citadel", klass: "foreign", origin: "us", aliasesKo: ["시타델"], aliasesEn: ["citadel"] },
  { canonical: "Millennium", klass: "foreign", origin: "us", aliasesKo: ["밀레니엄"], aliasesEn: ["millennium"] },
  { canonical: "Bridgewater", klass: "foreign", origin: "us", aliasesKo: ["브리지워터"], aliasesEn: ["bridgewater"] },
];

const ALL_INVESTORS: InvestorRecord[] = [...KOREAN_ACTIVISTS, ...FOREIGN_HOLDERS];

export interface InvestorMatch {
  canonical: string;
  klass: InvestorClass;
  origin: InvestorRecord["origin"];
}

/**
 * Match a filer name against the full allowlist. Returns the matched
 * record's metadata, or null if no match.
 */
export function matchInvestor(filerName: string | null | undefined): InvestorMatch | null {
  if (!filerName) return null;
  const name = filerName.trim();
  if (!name) return null;
  const nameLower = name.toLowerCase();

  for (const rec of ALL_INVESTORS) {
    for (const alias of rec.aliasesKo) {
      if (alias && name.includes(alias)) {
        return { canonical: rec.canonical, klass: rec.klass, origin: rec.origin };
      }
    }
    for (const alias of rec.aliasesEn) {
      if (alias && nameLower.includes(alias)) {
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
