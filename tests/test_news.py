from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from koreanpulse.news import _parse_pub_date, classify_industries, fetch_industry_news


class TestClassifyIndustries:
    def test_semiconductor(self):
        tags = classify_industries("삼성전자, HBM 공급 확대")
        assert "semiconductor" in tags

    def test_battery(self):
        tags = classify_industries("LG에너지솔루션, 전고체 배터리 양산 시작")
        assert "battery" in tags

    def test_multi_label(self):
        tags = classify_industries("현대차, 전기차 배터리 합작법인 설립")
        assert "auto" in tags
        assert "battery" in tags

    def test_no_match(self):
        tags = classify_industries("오늘 날씨가 좋습니다")
        assert tags == []

    def test_defense(self):
        tags = classify_industries("한화에어로스페이스, K9 자주포 폴란드 수출")
        assert "defense" in tags

    def test_case_insensitive(self):
        # Korean keywords don't have casing, but English ones might
        tags = classify_industries("AI 반도체 수요 폭증")
        # Both AI and semiconductor keywords present
        assert "ai" in tags
        assert "semiconductor" in tags

    def test_english_keywords_added_2026_07_08(self):
        """English-native sources (koreaherald/zdnet) need English keyword
        recall — Korean-only keywords miss most of their vocabulary."""
        tags = classify_industries("Hanwha Ocean loses submarine bid to German shipbuilder")
        assert "shipbuilding" in tags

        defense_tags = classify_industries("Hanwha Aerospace signs new fighter jet arms deal")
        assert "defense" in defense_tags

    def test_english_semiconductor_keyword(self):
        tags = classify_industries("Local chipmaker posts record semiconductor exports")
        assert "semiconductor" in tags

    def test_english_no_match_still_empty(self):
        assert classify_industries("The weather is nice today") == []


class TestParsePubDate:
    """Regression tests for a bug found via live verification 2026-07-08:
    Korea Herald's RSS uses a colon-separated UTC offset ("+09:00") that
    `email.utils.parsedate_to_datetime` silently parses as *naive*
    (tzinfo=None) instead of raising — verified directly against
    cpython's stdlib behavior. Mixed with the tz-aware datetimes every
    other source produces, `sorted(articles, key=lambda a: a.published_at)`
    then raised `TypeError: can't compare offset-naive and offset-aware
    datetimes` — reproduced live against mcp.koreanpulse.dev before this
    fix (search_korean_industry_news 500'd on `sources=["koreaherald"]`).
    """

    def test_bare_offset_is_timezone_aware(self):
        dt = _parse_pub_date("Wed, 8 Jul 2026 01:33:13 +0900")
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=9)

    def test_colon_offset_is_recovered_as_timezone_aware(self):
        """The actual koreaherald bug case."""
        dt = _parse_pub_date("Tue, 07 Jul 2026 21:37:00 +09:00")
        assert dt.tzinfo is not None
        assert dt.hour == 21 and dt.minute == 37  # wall-clock value preserved
        assert dt.utcoffset().total_seconds() == 9 * 3600

    def test_negative_colon_offset(self):
        dt = _parse_pub_date("Tue, 07 Jul 2026 21:37:00 -05:00")
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == -5 * 3600

    def test_empty_value_falls_back_to_utc_now(self):
        dt = _parse_pub_date("")
        assert dt.tzinfo is not None

    def test_garbage_value_falls_back_to_utc_now(self):
        dt = _parse_pub_date("not a date at all")
        assert dt.tzinfo is not None

    def test_mixed_offset_styles_are_mutually_sortable(self):
        """The actual failure mode: sorting a bare-offset dt against a
        colon-offset dt must not raise."""
        a = _parse_pub_date("Wed, 8 Jul 2026 01:33:13 +0900")
        b = _parse_pub_date("Tue, 07 Jul 2026 21:37:00 +09:00")
        assert sorted([a, b], reverse=True) == [a, b]


# RSS fixtures keyed by host so a single MockTransport handler can serve
# per-source canned feeds in the fetch_industry_news integration tests below.
_KOREAHERALD_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
<title><![CDATA[Samsung posts record semiconductor profit]]></title>
<link>https://www.koreaherald.com/article/1</link>
<pubDate>Tue, 07 Jul 2026 10:00:00 +09:00</pubDate>
<description><![CDATA[chipmaker earnings]]></description>
</item>
</channel></rss>"""
# Note: real koreaherald pubDate uses a colon-separated offset ("+09:00")
# — this is deliberate, it reproduces the naive/aware sort bug fixed
# alongside these tests (see TestParsePubDate + the mixed-source test
# below) rather than a bare "+0900" offset like every other source.

_ETNEWS_RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item>
<title>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90 HBM \xea\xb3\xb5\xea\xb8\x89 \xed\x99\x95\xeb\x8c\x80</title>
<link>https://www.etnews.com/article/1</link>
<pubDate>Tue, 07 Jul 2026 10:00:00 +0900</pubDate>
<description></description>
</item>
</channel></rss>"""


class TestFetchIndustryNewsLanguageAware:
    """Added 2026-07-08 alongside the koreaherald/zdnet English-native
    sources — verifies the title_en pre-fill shortcut and that a Korean
    source's title_en still comes back empty for the translator to fill."""

    @pytest.mark.asyncio
    async def test_english_source_prefills_title_en_without_translation(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_KOREAHERALD_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(source_keys=["koreaherald"], client=client)
        finally:
            await client.aclose()

        assert len(articles) == 1
        a = articles[0]
        assert a.title_ko == "Samsung posts record semiconductor profit"
        # title_en pre-filled with the original — no ko->en round trip needed.
        assert a.title_en == a.title_ko
        assert "semiconductor" in a.industries

    @pytest.mark.asyncio
    async def test_korean_source_leaves_title_en_empty_for_translator(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_ETNEWS_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(source_keys=["etnews"], client=client)
        finally:
            await client.aclose()

        assert len(articles) == 1
        assert articles[0].title_en == ""  # left for the caller's translator


class TestFetchIndustryNewsRobustness:
    """A single source failing (timeout / 5xx / malformed XML) must not
    block the other sources' results — task 3 robustness sweep, 2026-07-08."""

    @pytest.mark.asyncio
    async def test_one_source_500_does_not_block_the_others(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            if "etnews" in request.url.host:
                return httpx.Response(500, content=b"internal error")
            return httpx.Response(200, content=_KOREAHERALD_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(
                source_keys=["etnews", "koreaherald"], client=client
            )
        finally:
            await client.aclose()

        # etnews failed silently (logged + skipped); koreaherald's item survives.
        assert len(articles) == 1
        assert articles[0].source_key == "koreaherald"

    @pytest.mark.asyncio
    async def test_source_timeout_does_not_raise(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("simulated timeout", request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(source_keys=["etnews"], client=client)
        finally:
            await client.aclose()
        assert articles == []

    @pytest.mark.asyncio
    async def test_malformed_xml_does_not_raise(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"<not-even-close-to-xml")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(source_keys=["etnews"], client=client)
        finally:
            await client.aclose()
        assert articles == []

    @pytest.mark.asyncio
    async def test_mixed_offset_styles_across_sources_do_not_crash_sort(self):
        """End-to-end reproduction of the live 2026-07-08 bug: etnews uses
        a bare "+0900" pubDate offset, koreaherald a colon "+09:00" one.
        `fetch_industry_news` sorts all_items by published_at across
        sources — this must not raise even when the two feeds mix offset
        styles (it did, live, before the `_parse_pub_date` fix)."""

        async def handler(request: httpx.Request) -> httpx.Response:
            if "etnews" in request.url.host:
                return httpx.Response(200, content=_ETNEWS_RSS)
            return httpx.Response(200, content=_KOREAHERALD_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(
                source_keys=["etnews", "koreaherald"], client=client
            )
        finally:
            await client.aclose()

        assert len(articles) == 2
        assert {a.source_key for a in articles} == {"etnews", "koreaherald"}


class TestFetchIndustryNewsAbnormalPayloads:
    """Round-2 live-probe codification: a 200 response whose body is NOT a
    well-formed RSS feed (maintenance HTML, truncated XML, empty body, a JSON
    error envelope, binary garbage) must degrade to an empty result — never
    leak a raw lxml/parse traceback to the MCP client. These fixtures mirror
    the abnormal payloads probed live against the RSS path; all are synthetic.
    """

    _ABNORMAL = {
        "empty_body": b"",
        "maintenance_html": (
            b"<!DOCTYPE html><html><body><h1>503 Service Unavailable</h1></body></html>"
        ),
        "truncated_xml": b"<?xml version='1.0'?><rss><channel><item><title>foo</tit",
        "valid_xml_not_rss": b"<?xml version='1.0'?><root><a>hi</a></root>",
        "json_error_envelope": b'{"error":"rate limited"}',
        "binary_garbage": b"\x00\x01\x02\x03garbage",
        "gzip_magic_undecoded": b"\x1f\x8b\x08\x00garbage",
    }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", list(_ABNORMAL))
    async def test_abnormal_payload_degrades_to_empty(self, name):
        body = self._ABNORMAL[name]

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(
                source_keys=["koreaherald"], client=client, limit=5
            )
        finally:
            await client.aclose()
        assert articles == []

    @pytest.mark.asyncio
    async def test_one_abnormal_source_does_not_block_a_healthy_one(self):
        """A garbage body from one source must not poison a sibling feed."""

        async def handler(request: httpx.Request) -> httpx.Response:
            if "etnews" in request.url.host:
                return httpx.Response(200, content=b"\x00garbage-not-xml")
            return httpx.Response(200, content=_KOREAHERALD_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            articles = await fetch_industry_news(
                source_keys=["etnews", "koreaherald"], client=client
            )
        finally:
            await client.aclose()
        assert [a.source_key for a in articles] == ["koreaherald"]
