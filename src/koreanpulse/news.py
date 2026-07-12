"""Korean industry news aggregator.

Pulls RSS feeds from Korean industry press where available. We deliberately
prefer RSS over HTML scraping — RSS endpoints are explicitly published-for-
syndication content and fall under fair use, while scraping HTML pages can
violate ToS and triggers anti-bot.

For sources without RSS (MK, ChosunBiz), v0 returns nothing rather than
scraping. We add proper licensed feeds in v0.2 once we contact the publishers.

Industry classification: keyword-based against the Korean title. Cheap, OK
recall. Replace with a fine-tuned classifier later if precision matters.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from lxml import etree

from agentprod import Throttle, retry_async

from koreanpulse.models import Article
from koreanpulse.sources import NEWS_SOURCES, NEWS_SOURCE_BY_KEY, NewsSource

logger = logging.getLogger(__name__)


# Per-source throttle. Conservative — be a good citizen.
_throttle = Throttle(capacity=2, refill_per_sec=2, jitter_ms=(50, 200))


# Industry keyword classifier — Korean keywords plus English variants (added
# 2026-07-08 for the koreaherald/zdnet English-native sources — Korean-only
# keywords miss most vocabulary in English-language articles). Multi-label.
INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "semiconductor": ("반도체", "메모리", "파운드리", "HBM", "DRAM", "낸드", "EUV", "ASML", "TSMC",
                       "semiconductor", "chipmaker"),
    "shipbuilding": ("조선", "LNG선", "컨테이너선", "VLCC", "수주", "도크", "선박", "현대중공업", "삼성중공업", "한화오션",
                      "shipbuilder", "shipyard", "submarine"),
    "battery": ("배터리", "이차전지", "전고체", "LFP", "양극재", "음극재", "분리막", "전해질", "LG에너지솔루션", "삼성SDI", "SK온",
                "ev battery", "battery maker"),
    "biotech": ("바이오", "신약", "임상", "FDA 승인", "셀트리온", "삼성바이오로직스", "유한양행", "한미약품", "CDMO",
                "biotech", "biosimilar", "clinical trial"),
    "defense": ("방산", "K-방산", "K2 전차", "FA-50", "K9 자주포", "한화에어로스페이스", "KAI", "현대로템", "LIG넥스원",
                "defense industry", "defence industry", "fighter jet", "arms deal"),
    "auto": ("자동차", "현대차", "기아", "전기차", "수소차", "EV", "자율주행",
             "automaker", "electric vehicle", "self-driving"),
    "ev_charging": ("충전소", "충전기", "전기차 충전", "급속충전", "ev charging", "charging station"),
    "ai": ("AI", "인공지능", "LLM", "생성형", "데이터센터", "엔비디아", "GPU",
           "artificial intelligence", "data center"),
    "steel": ("철강", "POSCO", "포스코", "현대제철", "고로", "전기로", "steelmaker"),
    "petrochem": ("석유화학", "에틸렌", "프로필렌", "LG화학", "롯데케미칼", "한화솔루션", "petrochemical"),
    "construction": ("건설", "분양", "수주잔고", "현대건설", "GS건설", "DL이앤씨", "homebuilder"),
    "fintech": ("핀테크", "토스", "카카오페이", "네이버페이", "마이데이터", "fintech"),
    "gaming": ("게임", "넥슨", "엔씨소프트", "크래프톤", "카카오게임즈", "video game", "gaming industry"),
    "ecommerce": ("이커머스", "쿠팡", "네이버쇼핑", "당근", "물류센터", "e-commerce", "online retail"),
    "telco": ("통신", "5G", "6G", "SKT", "KT", "LG유플러스", "telecom", "telecommunications"),
    "energy": ("원전", "SMR", "한전", "한수원", "에너지", "태양광", "풍력",
               "nuclear power", "renewable energy", "solar power"),
}


# 2026-07-12 — ASCII-only keywords (e.g. "DRAM", "AI") were substring-
# matched against the whole text, which produces real false positives:
# "dram" is a substring of "k-dramas", "ai" is a substring of "chairman".
# Korean keywords don't have this problem the same way (no equivalent
# short-Korean-substring-inside-an-unrelated-word collision observed) and
# Korean text has no consistent word-boundary tokenization to rely on, so
# they keep the original substring match. ASCII-only keywords instead match
# on a letter-boundary regex, precompiled once per industry at module load
# (not per classify_industries() call). Plain `\b` is too strict here:
# Korean text abuts ASCII terms without spaces ("AI반도체") and model names
# append digits ("HBM3E"), so only adjacent A-Z letters block a match —
# digits and Hangul act as boundaries. A trailing optional plural
# ("chipmakers", "GPUs") is also accepted.
_ASCII_ONLY_RE = re.compile(r"^[\x00-\x7f]+$")


def _is_ascii_keyword(keyword: str) -> bool:
    return bool(_ASCII_ONLY_RE.match(keyword))


def _build_industry_matchers() -> dict[str, tuple[Optional[re.Pattern[str]], tuple[str, ...]]]:
    matchers: dict[str, tuple[Optional[re.Pattern[str]], tuple[str, ...]]] = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        ascii_keywords = [kw for kw in keywords if _is_ascii_keyword(kw)]
        non_ascii_keywords = tuple(kw.lower() for kw in keywords if not _is_ascii_keyword(kw))
        pattern: Optional[re.Pattern[str]] = None
        if ascii_keywords:
            alternation = "|".join(re.escape(kw) for kw in ascii_keywords)
            pattern = re.compile(
                rf"(?<![A-Za-z])(?:{alternation})(?:e?s)?(?![A-Za-z])", re.IGNORECASE
            )
        matchers[industry] = (pattern, non_ascii_keywords)
    return matchers


_INDUSTRY_MATCHERS = _build_industry_matchers()


def classify_industries(title: str, body: str = "") -> list[str]:
    """Return list of industry tags hit by the title (and body if given)."""
    text = f"{title} {body}"
    text_lower = text.lower()
    out: list[str] = []
    for industry, (pattern, non_ascii_keywords) in _INDUSTRY_MATCHERS.items():
        if pattern is not None and pattern.search(text):
            out.append(industry)
            continue
        if any(kw in text_lower for kw in non_ascii_keywords):
            out.append(industry)
    return out


async def _fetch_rss(source: NewsSource, client: httpx.AsyncClient) -> list[dict]:
    """Fetch + parse one RSS feed. Returns list of {title, link, pubDate, description}."""
    if not source.rss_url:
        return []

    await _throttle.acquire(timeout=3.0, label=f"news:{source.key}")

    async def _call() -> httpx.Response:
        return await client.get(
            source.rss_url,
            headers={"User-Agent": "koreanpulse/0.0 (+https://koreanpulse.dev)"},
        )

    resp = await retry_async(_call, max_attempts=3, base_seconds=1.0)
    resp.raise_for_status()
    try:
        root = etree.fromstring(resp.content)
    except etree.XMLSyntaxError as exc:
        logger.warning("news: %s rss parse failed: %s", source.key, exc)
        return []

    items: list[dict] = []
    for item in root.findall(".//item"):
        items.append(
            {
                # lxml's XML parser only decodes the 5 predefined XML
                # entities (amp/lt/gt/quot/apos) — named HTML entities some
                # feeds embed in title/description (&nbsp;, &rsquo;, &mdash;,
                # &hellip;, ...) survive as literal text without this.
                "title": html.unescape((item.findtext("title") or "").strip()),
                "link": (item.findtext("link") or "").strip(),
                "pubDate": (item.findtext("pubDate") or "").strip(),
                "description": html.unescape((item.findtext("description") or "").strip()),
            }
        )
    return items


# RFC 2822 pubDate strings normally use a bare "+0900" offset, but some
# feeds (Korea Herald, observed live 2026-07-08) use a colon-separated
# "+09:00" instead. `email.utils.parsedate_to_datetime` doesn't recognize
# that form and, instead of raising, silently returns a *naive* datetime
# with the offset dropped. Mixing that with the tz-aware datetimes every
# other source produces then crashes `sorted(..., key=published_at)` with
# "can't compare offset-naive and offset-aware datetimes". Recover the
# offset ourselves whenever parsedate_to_datetime hands back a naive dt.
_TZ_OFFSET_RE = re.compile(r"([+-])(\d{2}):?(\d{2})\s*$")


def _parse_pub_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        match = _TZ_OFFSET_RE.search(value)
        if match:
            sign, hh, mm = match.groups()
            offset = timedelta(hours=int(hh), minutes=int(mm))
            if sign == "-":
                offset = -offset
            dt = dt.replace(tzinfo=timezone(offset))
        else:
            # No recoverable offset — assume UTC rather than leaving the
            # datetime naive (and un-sortable against the tz-aware rows).
            dt = dt.replace(tzinfo=timezone.utc)
    return dt


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_SNIPPET_MAX_CHARS = 300


def _make_snippet(description: str) -> str:
    """Plain-text excerpt from an RSS `description` field for `Article.snippet`.

    HTML entities are already decoded by `_fetch_rss` (`html.unescape`).
    This additionally strips any literal HTML tags some feeds embed in
    `<description>` (e.g. "<p>...</p>"), collapses whitespace/newlines,
    and truncates to `_SNIPPET_MAX_CHARS`. No additional network fetch —
    derived from the same feed item the title came from.
    """
    if not description:
        return ""
    text = _TAG_RE.sub(" ", description)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text[:_SNIPPET_MAX_CHARS]


async def fetch_industry_news(
    *,
    industries: Optional[list[str]] = None,
    source_keys: Optional[list[str]] = None,
    limit: int = 30,
    client: Optional[httpx.AsyncClient] = None,
) -> list[Article]:
    """Aggregate Korean industry news from configured RSS sources.

    Args:
        industries: optional list of tags from INDUSTRY_KEYWORDS to filter to.
            None = all.
        source_keys: optional list of source keys (etnews, hankyung, …).
            None = all sources with RSS.
        limit: max articles total.
        client: optional shared httpx client.

    Returns:
        Articles sorted by published_at descending. `summary_en` is empty —
        callers add translation/summary via the Translator on demand to stay
        cost-disciplined (see SPEC.md). `snippet` is filled directly from
        the RSS `description` (no LLM call, no extra network fetch).
    """
    sources = NEWS_SOURCES
    if source_keys:
        sources = tuple(NEWS_SOURCE_BY_KEY[k] for k in source_keys if k in NEWS_SOURCE_BY_KEY)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        all_items: list[Article] = []
        for src in sources:
            try:
                rows = await _fetch_rss(src, client)
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("news: %s fetch failed: %s", src.key, exc)
                continue
            for r in rows:
                if not r["title"] or not r["link"]:
                    continue
                tags = classify_industries(r["title"], r.get("description", ""))
                if industries and not (set(industries) & set(tags)):
                    continue
                all_items.append(
                    Article(
                        title_ko=r["title"],
                        # English-native sources (koreaherald) pre-fill
                        # title_en with the original headline — no LLM
                        # round-trip needed, and it avoids feeding English
                        # text into a ko->en translation prompt. `title_ko`
                        # then holds the original-language title regardless
                        # of source language (kept as `title_ko` rather than
                        # a new field to preserve the stable public schema).
                        title_en=r["title"] if src.language == "en" else "",
                        source_key=src.key,
                        source_name=src.name_ko,
                        url=r["link"],
                        published_at=_parse_pub_date(r["pubDate"]),
                        summary_en="",
                        snippet=_make_snippet(r.get("description", "")),
                        industries=tags,
                        relevance_score=min(1.0, 0.4 + 0.15 * len(tags)),
                        attribution=src.attribution,
                    )
                )
    finally:
        if owns_client:
            await client.aclose()

    all_items.sort(key=lambda a: a.published_at, reverse=True)
    return all_items[:limit]
