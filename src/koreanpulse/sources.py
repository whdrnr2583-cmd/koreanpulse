"""Source definitions for Korean industry news + filings.

Keep this file the single source of truth for *where* we pull data from. Each
entry declares attribution requirements and known ToS notes.

Adding a source: bump `version`, document robots.txt and any rate-limit you
observed in production. Anything not in this file is not supposed to be
fetched in v0.

## Candidates evaluated 2026-07-08 and REJECTED — do not add without a fresh
## ToS review, these three publish RSS-feed-specific (not just generic
## copyright-page) restrictions that go beyond the fair-use posture we rely
## on for etnews/hankyung/koreaherald/zdnet:

- 아시아경제 (Asia Economy, asiae.co.kr/rss/) — feed page states explicitly:
  "RSS 서비스는 비상업적 사용만 허용하고 있으며, 상업적 활용은 금지하고
  있습니다" (non-commercial use only, commercial use prohibited).
- 서울경제 (Seoul Economic Daily, sedaily.com/rss) — feed page states:
  "RSS 서비스를 활용한 다수 이용자 대상의 상업적 활용 및 AI학습 이용을
  금지합니다" (commercial use for multiple users AND AI-training use both
  explicitly prohibited).
- 연합뉴스 (Yonhap) — RSS terms restrict use to personal subscription in a
  single individual's own reader; republishing/exposing the feed to
  "다수의 이용자" (multiple users) through a website/service — which is
  exactly what an MCP tool response does — requires separate permission
  from the copyright holder.

koreanpulse is a commercial product surfaced to many end users through MCP
tool calls, so all three fail this bar even under a title+link+attribution-
only fair-use posture (no full-text republish). Revisit if any of these
publishers ships a syndication/API program with different terms.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NewsSource:
    """A Korean news source we pull from.

    Attributes:
        key: short stable id used in tool params.
        name_ko: Korean name (for citations).
        name_en: English label.
        rss_url: RSS feed (preferred over scraping when available).
        base_url: base for resolving relative article links.
        attribution: human-readable attribution string we MUST include in
            every summary returned to a tool caller.
        robots_check: when last we checked robots.txt (yyyy-mm-dd).
        rate_limit_hint: empirical, conservative requests/sec.
    """

    key: str
    name_ko: str
    name_en: str
    rss_url: str | None
    base_url: str
    attribution: str
    robots_check: str
    rate_limit_hint: float
    language: Literal["ko", "en"] = "ko"
    """Origin language of the feed's title/description text. "en" sources
    (e.g. koreaherald) publish English-native headlines — callers should
    skip the ko->en translation step for these and use the title as-is."""


# Industry-focused press. Order matters only for tie-breaks in display.
NEWS_SOURCES: tuple[NewsSource, ...] = (
    NewsSource(
        key="etnews",
        name_ko="전자신문",
        name_en="Electronic Times (etnews)",
        rss_url="https://rss.etnews.com/Section902.xml",
        base_url="https://www.etnews.com",
        attribution="Source: 전자신문 (etnews.com)",
        robots_check="2026-05-04",
        rate_limit_hint=1.0,
    ),
    NewsSource(
        key="mk",
        name_ko="매일경제",
        name_en="Maeil Business Newspaper",
        rss_url=None,  # MK retired their public RSS; respect their site terms
        base_url="https://www.mk.co.kr",
        attribution="Source: 매일경제 (mk.co.kr)",
        robots_check="2026-05-04",
        rate_limit_hint=0.5,
    ),
    NewsSource(
        key="chosunbiz",
        name_ko="조선비즈",
        name_en="ChosunBiz",
        rss_url=None,
        base_url="https://biz.chosun.com",
        attribution="Source: 조선비즈 (biz.chosun.com)",
        robots_check="2026-05-04",
        rate_limit_hint=0.5,
    ),
    NewsSource(
        key="hankyung",
        name_ko="한국경제",
        name_en="The Korea Economic Daily",
        rss_url="https://www.hankyung.com/feed/all-news",
        base_url="https://www.hankyung.com",
        attribution="Source: 한국경제 (hankyung.com)",
        robots_check="2026-05-04",
        rate_limit_hint=1.0,
    ),
    NewsSource(
        key="koreaherald",
        name_ko="코리아헤럴드",
        name_en="The Korea Herald",
        # Verified live 2026-07-08: real Business-category items (not an
        # empty/redirect stub — /rss/kh_Business, unlike /rss/Business
        # which 200s but returns 0 items). English-native, no RSS-specific
        # ToS restriction found (only the generic site copyright notice
        # that etnews/hankyung also carry) — robots.txt allows all crawlers.
        rss_url="https://www.koreaherald.com/rss/kh_Business",
        base_url="https://www.koreaherald.com",
        attribution="Source: The Korea Herald (koreaherald.com)",
        robots_check="2026-07-08",
        rate_limit_hint=1.0,
        language="en",
    ),
    NewsSource(
        key="zdnet",
        name_ko="지디넷코리아",
        name_en="ZDNet Korea",
        # Verified live 2026-07-08: standard WordPress feed at /feed/, IT
        # industry coverage. robots.txt Allow: / for all UAs; no RSS-
        # specific commercial/AI-training restriction found (only a
        # generic "Copyright (c) meganews" notice in the feed itself).
        rss_url="https://zdnet.co.kr/feed/",
        base_url="https://zdnet.co.kr",
        attribution="Source: 지디넷코리아 (zdnet.co.kr)",
        robots_check="2026-07-08",
        rate_limit_hint=1.0,
    ),
)

NEWS_SOURCE_BY_KEY: dict[str, NewsSource] = {s.key: s for s in NEWS_SOURCES}


# ── DART ────────────────────────────────────────────────────────────────────
# DART (전자공시시스템) is public, free, English-key supported.
# https://opendart.fss.or.kr/ — official OpenAPI.
DART_API_BASE = "https://opendart.fss.or.kr/api"
DART_ATTRIBUTION = "Source: DART (Financial Supervisory Service, opendart.fss.or.kr)"

DartFilingType = Literal[
    "A",  # 정기공시 (periodic)
    "B",  # 주요사항보고 (major events)
    "C",  # 발행공시 (issuance)
    "D",  # 지분공시 (shareholding)
    "E",  # 기타공시
    "F",  # 외부감사
    "G",  # 펀드공시
    "H",  # 자산유동화
    "I",  # 거래소공시
    "J",  # 공정위공시
]

DART_FILING_TYPE_LABELS: dict[str, tuple[str, str]] = {
    # code: (한글, English)
    "A": ("정기공시", "Periodic Disclosure"),
    "B": ("주요사항보고", "Major Event Report"),
    "C": ("발행공시", "Securities Issuance Disclosure"),
    "D": ("지분공시", "Shareholding Disclosure"),
    "E": ("기타공시", "Other Disclosures"),
    "F": ("외부감사관련", "External Audit Related"),
    "G": ("펀드공시", "Fund Disclosure"),
    "H": ("자산유동화", "Asset-Backed Securitization"),
    "I": ("거래소공시", "Exchange Disclosure"),
    "J": ("공정위공시", "Fair Trade Commission Disclosure"),
}
