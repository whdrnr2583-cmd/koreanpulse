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
    yield
    corp_code_mod._INDEX = []
    corp_code_mod._BY_NAME = {}
    corp_code_mod._BY_STOCK = {}
    corp_code_mod._BY_CORP = {}


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
