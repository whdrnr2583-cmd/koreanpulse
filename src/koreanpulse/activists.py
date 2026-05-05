"""Korean activist + foreign-holder allowlist + matchers.

Used by `monitor_activist_investors` (activists only) and
`monitor_foreign_holders` (foreign passive holders) MCP tools, plus the
daily-worker TS port at `daily-worker/src/activists.ts`. Keep both lists
in sync.

Maintenance: these lists go stale. Add entries as new activist funds
emerge or as more foreign managers begin filing Korean 5%-rule
disclosures. Refresh quarterly by scanning recent type-D filer names.

Sources for the activist list (verified active 2025–2026 in Korean filings):
- KCGI (Korea Corporate Governance Improvement) — Hanjin / Kumho disputes
- 얼라인파트너스 (Align Partners) — bank governance push
- 안다자산운용 (Anda Asset)
- 차파트너스 / 차파트너스자산운용 (Cha Partners)
- 트러스톤자산운용 (Truston Asset)
- 라이프자산운용 (Life Asset)
- 플랫폼파트너스 (Platform Partners)
- VIP자산운용 (VIP Asset Management)
- 강성부펀드 (KCGI sister vehicle)
- ValueAct Capital (occasional Korean filings)
- Elliott Management (rare Korean filings, kept for completeness)

Sources for the foreign-holder list — top-30 global asset managers and
sovereign wealth funds known to file Korean 5%-rule disclosures.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Literal, Optional


class InvestorClass(str, enum.Enum):
    ACTIVIST = "activist"     # funds known for governance pressure / 5%-rule plays
    FOREIGN = "foreign"       # large foreign passive holders (capital-flow indicator)


Origin = Literal["kr", "us", "uk", "eu", "other"]


@dataclass(frozen=True)
class InvestorRecord:
    canonical: str            # English label we surface to callers
    klass: InvestorClass
    origin: Origin
    aliases_ko: tuple[str, ...]   # Korean strings to substring-match against flr_nm
    aliases_en: tuple[str, ...]


@dataclass(frozen=True)
class InvestorMatch:
    canonical: str
    klass: InvestorClass
    origin: Origin


KOREAN_ACTIVISTS: tuple[InvestorRecord, ...] = (
    InvestorRecord(
        canonical="KCGI",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("KCGI", "케이씨지아이", "강성부펀드"),
        aliases_en=("kcgi",),
    ),
    InvestorRecord(
        canonical="Align Partners",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("얼라인파트너스", "얼라인 파트너스"),
        aliases_en=("align partners", "alignpartners"),
    ),
    InvestorRecord(
        canonical="Anda Asset",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("안다자산운용", "안다 자산운용"),
        aliases_en=("anda asset",),
    ),
    InvestorRecord(
        canonical="Cha Partners",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("차파트너스", "차파트너스자산운용", "차 파트너스"),
        aliases_en=("cha partners",),
    ),
    InvestorRecord(
        canonical="Truston Asset",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("트러스톤자산운용", "트러스톤 자산운용"),
        aliases_en=("truston asset",),
    ),
    InvestorRecord(
        canonical="Life Asset",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("라이프자산운용", "라이프 자산운용"),
        aliases_en=("life asset",),
    ),
    InvestorRecord(
        canonical="Platform Partners",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("플랫폼파트너스", "플랫폼 파트너스"),
        aliases_en=("platform partners",),
    ),
    InvestorRecord(
        canonical="VIP Asset Management",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        aliases_ko=("VIP자산운용", "VIP 자산운용", "브이아이피자산운용"),
        aliases_en=("vip asset",),
    ),
    InvestorRecord(
        canonical="ValueAct Capital",
        klass=InvestorClass.ACTIVIST,
        origin="us",
        aliases_ko=("밸류액트", "ValueAct"),
        aliases_en=("valueact",),
    ),
    InvestorRecord(
        canonical="Elliott Management",
        klass=InvestorClass.ACTIVIST,
        origin="us",
        aliases_ko=("엘리엇", "Elliott"),
        aliases_en=("elliott",),
    ),
)


# Foreign passive institutional holders. 5%-rule filings from these
# names indicate foreign capital flow into KOSPI/KOSDAQ tickers — the
# leading indicator of "foreign money is showing up in this stock."
FOREIGN_HOLDERS: tuple[InvestorRecord, ...] = (
    InvestorRecord("BlackRock", InvestorClass.FOREIGN, "us",
                   ("블랙록",), ("blackrock",)),
    InvestorRecord("Vanguard", InvestorClass.FOREIGN, "us",
                   ("뱅가드",), ("vanguard",)),
    InvestorRecord("State Street", InvestorClass.FOREIGN, "us",
                   ("스테이트 스트리트", "스테이트스트리트"), ("state street",)),
    InvestorRecord("Fidelity", InvestorClass.FOREIGN, "us",
                   ("피델리티",), ("fidelity",)),
    InvestorRecord("Capital Group", InvestorClass.FOREIGN, "us",
                   ("캐피털그룹", "캐피탈그룹"), ("capital group", "capital research")),
    InvestorRecord("T. Rowe Price", InvestorClass.FOREIGN, "us",
                   ("티로프라이스", "티 로 프라이스"), ("t. rowe price", "t rowe price")),
    InvestorRecord("Wellington Management", InvestorClass.FOREIGN, "us",
                   ("웰링턴",), ("wellington",)),
    InvestorRecord("Matthews Asia", InvestorClass.FOREIGN, "us",
                   ("매튜스아시아",), ("matthews asia",)),
    InvestorRecord("Templeton", InvestorClass.FOREIGN, "us",
                   ("템플턴",), ("templeton", "franklin templeton")),
    InvestorRecord("Aberdeen", InvestorClass.FOREIGN, "uk",
                   ("애버딘", "아버딘"), ("aberdeen", "abrdn")),
    InvestorRecord("Schroders", InvestorClass.FOREIGN, "uk",
                   ("슈로더",), ("schroders", "schroder")),
    InvestorRecord("Norges Bank (Norway SWF)", InvestorClass.FOREIGN, "eu",
                   ("노르웨이중앙은행", "노르웨이은행"), ("norges bank",)),
    InvestorRecord("GIC (Singapore SWF)", InvestorClass.FOREIGN, "other",
                   ("싱가포르투자청",), ("gic private", "gic pte")),
    InvestorRecord("Temasek", InvestorClass.FOREIGN, "other",
                   ("테마섹",), ("temasek",)),
    InvestorRecord("Goldman Sachs", InvestorClass.FOREIGN, "us",
                   ("골드만삭스", "골드만 삭스"), ("goldman sachs",)),
    InvestorRecord("JPMorgan", InvestorClass.FOREIGN, "us",
                   ("JP모간", "JP모건", "제이피모건"), ("jpmorgan", "jp morgan")),
    InvestorRecord("Morgan Stanley", InvestorClass.FOREIGN, "us",
                   ("모건스탠리", "모건 스탠리"), ("morgan stanley",)),
    InvestorRecord("Citadel", InvestorClass.FOREIGN, "us",
                   ("시타델",), ("citadel",)),
    InvestorRecord("Millennium", InvestorClass.FOREIGN, "us",
                   ("밀레니엄",), ("millennium",)),
    InvestorRecord("Bridgewater", InvestorClass.FOREIGN, "us",
                   ("브리지워터",), ("bridgewater",)),
)


# Single combined tuple for the full-allowlist matcher.
ALL_INVESTORS: tuple[InvestorRecord, ...] = KOREAN_ACTIVISTS + FOREIGN_HOLDERS


def match_investor(filer_name: Optional[str]) -> Optional[InvestorMatch]:
    """Match a filer name against the full allowlist.

    Returns the matched record's metadata (canonical / klass / origin),
    or None if no match. Matching is case-insensitive substring; Korean
    aliases match against the raw name, latin aliases against the
    lowercased name. A mixed string like "KCGI 자산운용" matches both layers.
    """
    if not filer_name:
        return None
    name = filer_name.strip()
    if not name:
        return None
    name_lower = name.lower()

    for rec in ALL_INVESTORS:
        for alias in rec.aliases_ko:
            if alias and alias in name:
                return InvestorMatch(rec.canonical, rec.klass, rec.origin)
        for alias in rec.aliases_en:
            if alias and alias in name_lower:
                return InvestorMatch(rec.canonical, rec.klass, rec.origin)
    return None


def match_activist(filer_name: Optional[str]) -> Optional[str]:
    """Activist-only matcher (backwards-compatible).

    Returns the canonical activist label if `filer_name` matches a known
    activist, else None. Foreign passive holders return None here even
    when matched in `match_investor`.
    """
    match = match_investor(filer_name)
    if match is None or match.klass is not InvestorClass.ACTIVIST:
        return None
    return match.canonical


def match_foreign_holder(filer_name: Optional[str]) -> Optional[InvestorMatch]:
    """Foreign-holder-only matcher.

    Returns the full match (so callers can surface origin / canonical),
    or None if `filer_name` is not in `FOREIGN_HOLDERS`.
    """
    match = match_investor(filer_name)
    if match is None or match.klass is not InvestorClass.FOREIGN:
        return None
    return match
