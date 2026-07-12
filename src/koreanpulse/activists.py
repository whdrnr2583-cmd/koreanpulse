"""Korean activist + foreign-holder allowlist + matchers.

Used by `monitor_activist_investors` (activists only) and
`monitor_foreign_holders` (foreign passive holders) MCP tools, plus the
daily-worker TS port at `daily-worker/src/activists.ts`. Keep both lists
in sync.

Maintenance: these lists go stale. Add entries as new activist funds
emerge or as more foreign managers begin filing Korean 5%-rule
disclosures. Refresh quarterly by scanning recent type-D filer names.

Sources for the activist list (verified active 2025–2026 in Korean filings —
refreshed 2026-07-08, see per-entry comments below for the news citation
that grounds each addition):
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
- 머스트자산운용 (Must Asset Management) — 영풍/파마리서치/리파인 campaigns 2024–2026
- 달튼인베스트먼트 (Dalton Investments) — 콜마홀딩스 board seat 2025, 슈프리마 5% stake 2026
- 플래시라이트캐피탈파트너스 (Flashlight Capital Partners / FCP) — KT&G, 에스원 campaigns 2025
- 오아시스매니지먼트 (Oasis Management) — KT&G stake, building out a Korea desk 2025
- 팰리서캐피탈 (Palliser Capital) — 삼성물산/SK스퀘어/LG화학 campaigns 2023–2025
- 화이트박스 / Whitebox Advisors — 삼성물산 shareholder proposal campaign
- 시티오브런던 (City of London Investment Management / CLIM) — 삼성물산 campaign 2024

Sources for the foreign-holder list — top-30 global asset managers and
sovereign wealth funds known to file Korean 5%-rule disclosures. Spot-checked
2026-07-08: BlackRock confirmed still actively crossing 5% on Samsung
Electronics / POSCO Holdings / Hyundai Rotem as of April 2026 — no changes
needed to this list this cycle.
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
    # Added 2026-07-08 — verified via 2024-2026 Korean press (Herald Biz,
    # Newsis, Edaily) that each of the below ran an active campaign or
    # crossed a 5%-rule disclosure on a KOSPI/KOSDAQ name in 2025-2026.
    InvestorRecord(
        canonical="Must Asset Management",
        klass=InvestorClass.ACTIVIST,
        origin="kr",
        # 영풍 (2024, treasury-share cancellation demand), 파마리서치 (spin-off
        # pushback), 리파인 (9.85% stake, 2026 capital-reserve campaign).
        aliases_ko=("머스트자산운용", "머스트 자산운용"),
        aliases_en=("must asset management", "must asset"),
    ),
    InvestorRecord(
        canonical="Dalton Investments",
        klass=InvestorClass.ACTIVIST,
        origin="us",
        # 콜마홀딩스 board seat won at 2025-03-31 AGM after converting to
        # "management participation" purpose; 슈프리마 5.05% stake 2026-05-26.
        aliases_ko=("달튼인베스트먼트", "달튼인베스트먼트코리아", "달튼 인베스트먼트"),
        aliases_en=("dalton investments",),
    ),
    InvestorRecord(
        canonical="Flashlight Capital Partners",
        klass=InvestorClass.ACTIVIST,
        origin="other",  # Singapore-registered; Korea-focused campaigns
        # KT&G stake + 에스원 (S-1) governance campaign, both active 2025.
        aliases_ko=("플래시라이트캐피탈파트너스", "플래시라이트캐피탈"),
        aliases_en=("flashlight capital",),
    ),
    InvestorRecord(
        canonical="Oasis Management",
        klass=InvestorClass.ACTIVIST,
        origin="other",  # Hong Kong-based
        # KT&G's first Korean position (~1.5%); stood up a Korea investment
        # team in 2025 ahead of expected full activist campaigns.
        aliases_ko=("오아시스매니지먼트", "오아시스 매니지먼트"),
        aliases_en=("oasis management",),
    ),
    InvestorRecord(
        canonical="Palliser Capital",
        klass=InvestorClass.ACTIVIST,
        origin="uk",
        # 삼성물산 (2023) -> SK스퀘어 (2024) -> LG화학 (2025) shareholder
        # proposal campaigns; founded by ex-Elliott Hong Kong CIO James Smith.
        aliases_ko=("팰리서캐피탈", "팰리서 캐피탈"),
        aliases_en=("palliser capital",),
    ),
    InvestorRecord(
        canonical="Whitebox Advisors",
        klass=InvestorClass.ACTIVIST,
        origin="us",
        # Joined City of London + Palliser on the 2022-2024 삼성물산
        # buyback/dividend shareholder-proposal campaign.
        aliases_ko=("화이트박스", "화이트박스어드바이저스"),
        aliases_en=("whitebox advisors",),
    ),
    InvestorRecord(
        canonical="City of London Investment Management",
        klass=InvestorClass.ACTIVIST,
        origin="uk",
        # Paired with Anda Asset on a 삼성물산 dividend/buyback shareholder
        # proposal at the 2024 AGM.
        aliases_ko=("시티오브런던",),
        aliases_en=("city of london investment",),
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


# 2026-07-12 — a few allowlist aliases are short enough to also appear
# inside an unrelated real-world name's substring, producing a false
# activist/foreign-holder tag on a filer that has nothing to do with the
# fund. Keyed by `InvestorRecord.canonical`; each value is a tuple of
# substrings that, when present in the filer name, block a match against
# that record entirely (checked before the alias scan below).
_ALIAS_DENYLIST: dict[str, tuple[str, ...]] = {
    # "웰링턴" alone also matches the Daniel Wellington watch brand's
    # Korean subsidiary/importer naming ("다니엘웰링턴...").
    "Wellington Management": ("다니엘웰링턴",),
    # "캐피탈그룹"/"캐피털그룹" also matches "제일캐피탈그룹" and other
    # "제일캐피탈"-prefixed Korean consumer-finance entities, unrelated to
    # The Capital Group Companies.
    "Capital Group": ("제일캐피탈",),
    # Bare "밀레니엄" also matches several real, unrelated DART-registered
    # non-fund entities (verified against the corp_code registry) rather
    # than Millennium Management: a Shilla-affiliated hospitality entity,
    # a Daedong-affiliated entity, and an unrelated holding company.
    "Millennium": ("신라밀레니엄", "대동밀레니엄", "밀레니엄홀딩스"),
}


def match_investor(filer_name: Optional[str]) -> Optional[InvestorMatch]:
    """Match a filer name against the full allowlist.

    Returns the matched record's metadata (canonical / klass / origin),
    or None if no match. Matching is case-insensitive substring; Korean
    aliases match against the raw name, latin aliases against the
    lowercased name. A mixed string like "KCGI 자산운용" matches both layers.

    A record listed in `_ALIAS_DENYLIST` is skipped entirely (not just the
    offending alias) when the filer name contains one of its denylisted
    substrings — this only suppresses false positives for that record; the
    scan continues so unrelated allowlist entries can still match.
    """
    if not filer_name:
        return None
    name = filer_name.strip()
    if not name:
        return None
    name_lower = name.lower()

    for rec in ALL_INVESTORS:
        denylist = _ALIAS_DENYLIST.get(rec.canonical, ())
        if denylist and any(bad in name for bad in denylist):
            continue
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
