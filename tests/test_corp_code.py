"""Tests for the DART corp_code resolver — index parsing, lookups, and the
robustness fix for malformed/error download responses (2026-07-08).

Previously `_download_corp_code` had two unhandled failure modes
(zipfile.BadZipFile, StopIteration on a ZIP with no .xml member) that would
surface a raw Python traceback to MCP clients whenever DART_API_KEY was
invalid or the daily quota was exhausted — DART returns a small error body
(not the corp index ZIP) in that case. `CorpCodeError` now wraps both.
"""
from __future__ import annotations

import io
import zipfile

import httpx
import pytest

import koreanpulse.corp_code as corp_code_mod
from koreanpulse.corp_code import (
    CorpCodeError,
    _download_corp_code,
    _parse_xml,
    ensure_index_loaded,
    lookup_by_corp_code,
    lookup_by_name,
    lookup_by_stock_code,
)


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result>
    <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <stock_code>005930</stock_code>
        <modify_date>20260101</modify_date>
    </list>
    <list>
        <corp_code>00999999</corp_code>
        <corp_name>비상장회사</corp_name>
        <stock_code></stock_code>
        <modify_date>20260101</modify_date>
    </list>
</result>
""".encode("utf-8")


def _zip_bytes(xml_bytes: bytes, name: str = "CORPCODE.xml") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, xml_bytes)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_index():
    """Each test starts with a clean in-memory index."""
    corp_code_mod._INDEX = []
    corp_code_mod._BY_NAME = {}
    corp_code_mod._BY_STOCK = {}
    corp_code_mod._BY_CORP = {}
    corp_code_mod._NORM_NAMES = []
    corp_code_mod._LOADED_AT = 0.0
    yield
    corp_code_mod._INDEX = []
    corp_code_mod._BY_NAME = {}
    corp_code_mod._BY_STOCK = {}
    corp_code_mod._BY_CORP = {}
    corp_code_mod._NORM_NAMES = []
    corp_code_mod._LOADED_AT = 0.0


@pytest.fixture(autouse=True)
def _isolate_cache_dir(tmp_path, monkeypatch):
    """Never touch the real .data/dart cache from tests."""
    cache_dir = tmp_path / "dart_cache"
    monkeypatch.setattr(corp_code_mod, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(corp_code_mod, "CACHE_FILE", cache_dir / "corpCode.xml")


def _mock_client_factory(mock_handler):
    """Build a stand-in for `httpx.AsyncClient` that routes through a
    MockTransport. `_download_corp_code` constructs its own client
    internally (no injectable `client=` param), so we patch the class."""
    real_async_client = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        return real_async_client(*args, **kwargs)

    return _factory


class TestParseXml:
    def test_parses_entries(self):
        entries = _parse_xml(SAMPLE_XML)
        assert len(entries) == 2
        assert entries[0].corp_code == "00126380"
        assert entries[0].corp_name == "삼성전자"
        assert entries[0].stock_code == "005930"

    def test_unlisted_stock_code_is_none(self):
        entries = _parse_xml(SAMPLE_XML)
        assert entries[1].stock_code is None

    def test_skips_rows_missing_required_fields(self):
        xml = b"<result><list><corp_code></corp_code><corp_name>Foo</corp_name></list></result>"
        assert _parse_xml(xml) == []

    def test_malformed_xml_raises_corp_code_error_not_lxml(self):
        """A truncated cache file (partial write) must not leak a raw
        lxml XMLSyntaxError to MCP clients."""
        truncated = b"<result><list><corp_code>001"
        with pytest.raises(CorpCodeError, match="malformed"):
            _parse_xml(truncated)


class TestDownloadCorpCode:
    @pytest.mark.asyncio
    async def test_no_api_key_raises_corp_code_error(self, monkeypatch):
        monkeypatch.delenv("DART_API_KEY", raising=False)
        with pytest.raises(CorpCodeError, match="DART_API_KEY"):
            await _download_corp_code()

    @pytest.mark.asyncio
    async def test_bad_zip_raises_clear_corp_code_error(self, monkeypatch):
        """DART returns a small error body (not a ZIP) for an invalid key
        or exhausted quota — must not leak a raw zipfile.BadZipFile trace."""
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b'{"status":"020","message":"quota exceeded"}')

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        with pytest.raises(CorpCodeError, match="not the expected ZIP"):
            await _download_corp_code()

    @pytest.mark.asyncio
    async def test_zip_with_no_xml_member_raises_clear_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", b"not an xml file")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=buf.getvalue())

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        with pytest.raises(CorpCodeError, match="not the expected ZIP"):
            await _download_corp_code()

    @pytest.mark.asyncio
    async def test_http_error_wrapped_in_corp_code_error(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, content=b"service unavailable")

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        with pytest.raises(CorpCodeError, match="download failed"):
            await _download_corp_code()

    @pytest.mark.asyncio
    async def test_non_2xx_status_never_leaks_api_key_in_error_text(self, monkeypatch):
        """A transient non-2xx from DART (maintenance/rate-limit/5xx) must
        never carry DART_API_KEY in the raised CorpCodeError text.

        `crtfc_key` rides on the query string (see `_download_corp_code`'s
        `params=`), and httpx.HTTPStatusError's own message template embeds
        the full request URL (`"... for url '{0.url}'"`) — interpolating the
        raw exception object into the error message would leak the key to
        any caller of the two free/anonymous tools that trigger this path
        (`lookup_corp_code`, `resolve_stock_code`), no license required.
        `str(CorpCodeError(...))` is exactly what FastMCP's dispatcher embeds
        verbatim into the client-facing ToolError text (`f"...: {e}"`), so
        that's the surface this test guards.
        """
        secret_key = "SUPER_SECRET_DART_KEY_12345"
        monkeypatch.setenv("DART_API_KEY", secret_key)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, content=b"service unavailable")

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        with pytest.raises(CorpCodeError) as exc_info:
            await _download_corp_code()
        assert secret_key not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transport_error_never_leaks_api_key_in_error_text(self, monkeypatch):
        """Same guarantee as above for non-status httpx errors (connect/read
        timeouts, transport failures) — these don't embed the URL in their
        own message today, but assert it explicitly so the invariant can't
        regress silently if httpx's exception formatting ever changes."""
        secret_key = "SUPER_SECRET_DART_KEY_12345"
        monkeypatch.setenv("DART_API_KEY", secret_key)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        with pytest.raises(CorpCodeError) as exc_info:
            await _download_corp_code()
        assert secret_key not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_download_extracts_xml(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        zip_bytes = _zip_bytes(SAMPLE_XML)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        xml_bytes = await _download_corp_code()
        assert b"\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90" in xml_bytes  # 삼성전자 utf-8


class TestEnsureIndexLoadedEndToEnd:
    @pytest.mark.asyncio
    async def test_loads_and_indexes(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        zip_bytes = _zip_bytes(SAMPLE_XML)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        n = await ensure_index_loaded(force_refresh=True)
        assert n == 2

        hit = await lookup_by_stock_code("005930")
        assert hit is not None
        assert hit.corp_name == "삼성전자"

        by_corp = await lookup_by_corp_code("00126380")
        assert by_corp is not None
        assert by_corp.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_corrupt_disk_cache_recovers_by_refetching(self, monkeypatch):
        """A corrupt (truncated) fresh disk cache must self-heal by
        re-downloading — not fail on every call for the whole 7-day TTL."""
        monkeypatch.setenv("DART_API_KEY", "test_key")

        # Seed a "fresh" but corrupt cache file on disk.
        corp_code_mod.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        corp_code_mod.CACHE_FILE.write_bytes(b"<result><list><corp_code>001")
        assert corp_code_mod._is_cache_fresh()  # just written → within TTL

        zip_bytes = _zip_bytes(SAMPLE_XML)

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(mock_handler))
        # force_refresh=False so it goes through the fresh-cache path and
        # exercises the corrupt-cache recovery branch specifically.
        n = await ensure_index_loaded(force_refresh=False)
        assert n == 2
        # Cache file was rewritten with the good download.
        assert b"\xec\x82\xbc\xec\x84\xb1" in corp_code_mod.CACHE_FILE.read_bytes()


class TestLookups:
    """Lookup-only tests seed the in-memory index directly — no network."""

    @pytest.fixture(autouse=True)
    def _seed(self):
        from koreanpulse.corp_code import CorpEntry

        entries = [
            CorpEntry("00126380", "삼성전자", "005930", "20260101"),
            CorpEntry("00164779", "SK하이닉스", "000660", "20260101"),
            CorpEntry("00999999", "삼성전자서비스", None, "20260101"),
        ]
        corp_code_mod._INDEX = entries
        corp_code_mod._BY_NAME = {e.corp_name: e for e in entries}
        corp_code_mod._BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
        corp_code_mod._BY_CORP = {e.corp_code: e for e in entries}

    @pytest.mark.asyncio
    async def test_lookup_by_name_substring_matches_multiple(self):
        hits = await lookup_by_name("삼성전자")
        assert len(hits) == 2  # 삼성전자 + 삼성전자서비스

    @pytest.mark.asyncio
    async def test_lookup_by_name_listed_only_filters_unlisted(self):
        hits = await lookup_by_name("삼성전자", listed_only=True)
        assert len(hits) == 1
        assert hits[0].corp_name == "삼성전자"

    @pytest.mark.asyncio
    async def test_lookup_by_name_empty_query_returns_empty(self):
        assert await lookup_by_name("") == []
        assert await lookup_by_name("   ") == []

    @pytest.mark.asyncio
    async def test_lookup_by_name_respects_limit(self):
        hits = await lookup_by_name("삼성전자", limit=1)
        assert len(hits) == 1

    @pytest.mark.asyncio
    async def test_lookup_by_stock_code_unknown_returns_none(self):
        assert await lookup_by_stock_code("999999") is None

    @pytest.mark.asyncio
    async def test_lookup_by_stock_code_found(self):
        hit = await lookup_by_stock_code("000660")
        assert hit is not None
        assert hit.corp_name == "SK하이닉스"

    @pytest.mark.asyncio
    async def test_lookup_by_corp_code_unknown_returns_none(self):
        assert await lookup_by_corp_code("00000001") is None


class TestCorpResolverRanking:
    """2026-07-12 accuracy fix — `lookup_by_name` used to early-break on
    `limit` while scanning raw index order, so an exact-name match sitting
    later in the index could be silently outranked by an earlier unrelated
    substring hit (real symptom: '삼성전자' wasn't `result[0]`, '셀트리온'
    exact match landed at index 2). The fixtures below deliberately place
    the exact/listed/shorter match *later* in raw index order to prove the
    new ranking (not scan order) decides the winner."""

    @pytest.fixture(autouse=True)
    def _seed(self):
        from koreanpulse.corp_code import CorpEntry

        entries = [
            # 삼성전자 cluster — exact/listed match placed last in raw order.
            CorpEntry("00000010", "삼성전자서비스", None, "20250101"),
            CorpEntry("00000011", "삼성전자판매", "010010", "20260101"),
            CorpEntry("00000012", "삼성전자", "005930", "20260101"),
            # 셀트리온 cluster — exact match placed last (index 2 within the
            # cluster), longer substring matches placed earlier.
            CorpEntry("00000020", "셀트리온제약", "068760", "20260101"),
            CorpEntry("00000021", "셀트리온헬스케어", "091990", "20260101"),
            CorpEntry("00000022", "셀트리온", "068270", "20260101"),
        ]
        corp_code_mod._INDEX = entries
        corp_code_mod._BY_NAME = {e.corp_name: e for e in entries}
        corp_code_mod._BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
        corp_code_mod._BY_CORP = {e.corp_code: e for e in entries}

    @pytest.mark.asyncio
    async def test_exact_listed_match_ranks_first_despite_scan_order(self):
        hits = await lookup_by_name("삼성전자")
        assert hits[0].corp_name == "삼성전자"
        assert hits[0].stock_code == "005930"

    @pytest.mark.asyncio
    async def test_exact_match_ranks_first_despite_scan_order(self):
        hits = await lookup_by_name("셀트리온")
        assert hits[0].corp_name == "셀트리온"
        assert hits[0].stock_code == "068270"

    @pytest.mark.asyncio
    async def test_limit_applied_after_ranking_not_before(self):
        # With limit=1 the single returned hit must still be the exact
        # match, not whatever the scan happened to see first.
        hits = await lookup_by_name("삼성전자", limit=1)
        assert len(hits) == 1
        assert hits[0].corp_name == "삼성전자"


class TestLookupByStockCodeNormalization:
    """2026-07-12 accuracy fix — real-world tickers often carry a leading
    zero drop or an exchange suffix (Yahoo/Bloomberg-style '.KS'/'.KQ')."""

    @pytest.fixture(autouse=True)
    def _seed(self):
        from koreanpulse.corp_code import CorpEntry

        entries = [CorpEntry("00126380", "삼성전자", "005930", "20260101")]
        corp_code_mod._INDEX = entries
        corp_code_mod._BY_NAME = {e.corp_name: e for e in entries}
        corp_code_mod._BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
        corp_code_mod._BY_CORP = {e.corp_code: e for e in entries}

    @pytest.mark.asyncio
    async def test_leading_zero_dropped_ticker_resolves(self):
        hit = await lookup_by_stock_code("5930")
        assert hit is not None
        assert hit.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_ks_suffix_stripped(self):
        hit = await lookup_by_stock_code("005930.KS")
        assert hit is not None
        assert hit.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_whitespace_and_leading_zero_both_handled(self):
        hit = await lookup_by_stock_code(" 5930 ")
        assert hit is not None
        assert hit.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_krx_suffix_stripped(self):
        hit = await lookup_by_stock_code("005930.KRX")
        assert hit is not None
        assert hit.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_kq_suffix_stripped_lowercase(self):
        hit = await lookup_by_stock_code("005930.kq")
        assert hit is not None
        assert hit.stock_code == "005930"

    @pytest.mark.asyncio
    async def test_still_returns_none_for_unknown_code(self):
        assert await lookup_by_stock_code("999999") is None


def _seed(entries):
    corp_code_mod._install(entries)


class TestNameNormalizationAndAliases:
    @pytest.fixture(autouse=True)
    def _seed_index(self):
        from koreanpulse.corp_code import CorpEntry

        _seed(
            [
                CorpEntry("00126380", "삼성전자", "005930", "20260101"),
                CorpEntry("00164779", "SK하이닉스", "000660", "20260101"),
                CorpEntry("00266961", "NAVER", "035420", "20260101"),
                CorpEntry("00258801", "카카오", "035720", "20260101"),
                CorpEntry("00999998", "(주)케이티앤지서비스", None, "20260101"),
            ]
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("q", ["sk하이닉스", "SK 하이닉스", "Sk하이닉스", "ＳＫ하이닉스"])
    async def test_case_width_and_spacing_insensitive(self, q):
        hits = await lookup_by_name(q)
        assert [h.corp_name for h in hits] == ["SK하이닉스"]

    @pytest.mark.asyncio
    async def test_lowercase_latin_name(self):
        assert [h.corp_name for h in await lookup_by_name("naver")] == ["NAVER"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "q,expected",
        [
            ("Samsung Electronics", "삼성전자"),
            ("SK hynix", "SK하이닉스"),
            ("kakao", "카카오"),
        ],
    )
    async def test_english_names_resolve_via_alias(self, q, expected):
        hits = await lookup_by_name(q)
        assert hits and hits[0].corp_name == expected

    @pytest.mark.asyncio
    async def test_unknown_english_name_returns_empty_not_garbage(self):
        assert await lookup_by_name("Acme Widgets Ltd") == []

    @pytest.mark.asyncio
    async def test_alias_never_invents_entries_missing_from_index(self):
        # "Hyundai Motor" maps to 현대자동차, which is not in this index.
        assert await lookup_by_name("Hyundai Motor") == []

    @pytest.mark.asyncio
    async def test_limit_zero_or_negative_returns_nothing(self):
        assert await lookup_by_name("삼성", limit=0) == []
        assert await lookup_by_name("삼성", limit=-3) == []


class TestIndexRefreshRobustness:
    @pytest.mark.asyncio
    async def test_concurrent_first_calls_download_once(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        zip_bytes = _zip_bytes(SAMPLE_XML)
        calls = {"n": 0}

        import asyncio

        async def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            await asyncio.sleep(0.02)  # a real suspension point, like network I/O
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))

        results = await asyncio.gather(*[ensure_index_loaded() for _ in range(6)])
        assert results == [2] * 6
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_failed_refresh_keeps_stale_disk_cache(self, monkeypatch):
        """An expired disk cache + a DART outage must not break lookups."""
        import os
        import time as _time

        monkeypatch.setenv("DART_API_KEY", "test_key")
        corp_code_mod.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        corp_code_mod.CACHE_FILE.write_bytes(SAMPLE_XML)
        old = _time.time() - corp_code_mod.CACHE_TTL_SECONDS - 3600
        os.utime(corp_code_mod.CACHE_FILE, (old, old))
        assert not corp_code_mod._is_cache_fresh()

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="down")

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
        assert await ensure_index_loaded() == 2

    @pytest.mark.asyncio
    async def test_failed_refresh_without_any_cache_still_raises(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="down")

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
        with pytest.raises(CorpCodeError, match="HTTP 503"):
            await ensure_index_loaded()

    @pytest.mark.asyncio
    async def test_in_memory_index_is_refreshed_after_ttl(self, monkeypatch):
        """A server left running for weeks must pick up new listings."""
        import time as _time

        monkeypatch.setenv("DART_API_KEY", "test_key")
        zip_bytes = _zip_bytes(SAMPLE_XML)
        calls = {"n": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
        await ensure_index_loaded()
        assert calls["n"] == 1
        await ensure_index_loaded()
        assert calls["n"] == 1  # still fresh in memory

        corp_code_mod._LOADED_AT = _time.time() - corp_code_mod.CACHE_TTL_SECONDS - 10
        # the disk copy is also treated as expired
        import os

        old = _time.time() - corp_code_mod.CACHE_TTL_SECONDS - 10
        os.utime(corp_code_mod.CACHE_FILE, (old, old))
        await ensure_index_loaded()
        assert calls["n"] == 2

    @pytest.mark.asyncio
    async def test_unwritable_cache_dir_does_not_break_loading(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        blocker = tmp_path / "file_not_dir"
        blocker.write_text("x")
        monkeypatch.setattr(corp_code_mod, "CACHE_DIR", blocker / "dart")
        monkeypatch.setattr(corp_code_mod, "CACHE_FILE", blocker / "dart" / "corpCode.xml")
        zip_bytes = _zip_bytes(SAMPLE_XML)

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
        assert await ensure_index_loaded() == 2

    @pytest.mark.asyncio
    async def test_cache_write_is_atomic_no_tmp_left_behind(self, monkeypatch):
        monkeypatch.setenv("DART_API_KEY", "test_key")
        zip_bytes = _zip_bytes(SAMPLE_XML)

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=zip_bytes)

        monkeypatch.setattr(httpx, "AsyncClient", _mock_client_factory(handler))
        await ensure_index_loaded()
        names = sorted(p.name for p in corp_code_mod.CACHE_DIR.iterdir())
        assert names == ["corpCode.xml"]


class TestDataDir:
    def test_explicit_env_wins(self, monkeypatch, tmp_path):
        from koreanpulse import _paths

        monkeypatch.setattr(_paths, "_RESOLVED", None)
        monkeypatch.setenv("KOREANPULSE_DATA_DIR", str(tmp_path / "kp"))
        assert _paths.data_dir() == tmp_path / "kp"
        assert (tmp_path / "kp").is_dir()

    def test_unwritable_cwd_falls_back_to_home(self, monkeypatch, tmp_path):
        """MCP hosts often launch with cwd=/ — this used to crash at import."""
        from koreanpulse import _paths

        monkeypatch.setattr(_paths, "_RESOLVED", None)
        monkeypatch.delenv("KOREANPULSE_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home").mkdir()
        real = _paths._writable_dir

        def fake(path):
            return False if str(path) == ".data" else real(path)

        monkeypatch.setattr(_paths, "_writable_dir", fake)
        assert _paths.data_dir() == tmp_path / "home" / ".koreanpulse"
