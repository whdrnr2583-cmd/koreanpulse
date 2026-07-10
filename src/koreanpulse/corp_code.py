"""DART corp-code resolver.

DART identifies companies by an 8-digit `corp_code`, distinct from the KRX
6-digit stock_code. The mapping lives in a single XML file (~5MB) downloaded
from `corpCode.xml`. We download once, parse, build an in-memory index, and
serve name → corp_code lookups instantly.

Refresh policy: cache the file to disk for 7 days. Companies rarely move corp
codes, so this is plenty fresh.
"""
from __future__ import annotations

import io
import logging
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from lxml import etree

logger = logging.getLogger(__name__)


CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
CACHE_DIR = Path(".data/dart")
CACHE_FILE = CACHE_DIR / "corpCode.xml"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days


@dataclass(frozen=True)
class CorpEntry:
    """One entry from DART's corp index."""

    corp_code: str   # 8-digit
    corp_name: str   # Korean
    stock_code: Optional[str]  # 6-digit KRX or None for unlisted
    modify_date: str  # YYYYMMDD


_INDEX: list[CorpEntry] = []
_BY_NAME: dict[str, CorpEntry] = {}
_BY_STOCK: dict[str, CorpEntry] = {}
_BY_CORP: dict[str, CorpEntry] = {}


class CorpCodeError(RuntimeError):
    """Raised when the corp_code index can't be downloaded or parsed."""


def _api_key() -> str:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        raise CorpCodeError(
            "DART_API_KEY env var is missing. "
            "Get one at https://opendart.fss.or.kr/ and set it before calling DART tools."
        )
    return key


async def _download_corp_code() -> bytes:
    """Fetch corpCode.zip and return the xml bytes inside.

    Raises:
        CorpCodeError: on network failure, non-2xx status, or a response
            body that isn't the expected ZIP-of-one-XML shape (this is
            what DART returns for an invalid/quota-exhausted API key —
            a small error body instead of the corp index ZIP, so we
            surface a clear message instead of a raw zipfile traceback).
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(CORP_CODE_URL, params={"crtfc_key": _api_key()})
            resp.raise_for_status()
            content = resp.content
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise CorpCodeError(f"corp_code index download failed: {exc}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_name = next(n for n in zf.namelist() if n.endswith(".xml"))
            return zf.read(xml_name)
    except (zipfile.BadZipFile, StopIteration) as exc:
        raise CorpCodeError(
            "corp_code index response was not the expected ZIP-of-XML — "
            "this usually means DART_API_KEY is invalid or the daily DART "
            "quota is exhausted. Verify the key at https://opendart.fss.or.kr/."
        ) from exc


def _is_cache_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age = time.time() - CACHE_FILE.stat().st_mtime
    return age < CACHE_TTL_SECONDS


def _parse_xml(xml_bytes: bytes) -> list[CorpEntry]:
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        # A truncated disk cache (partial write on disk-full / killed process)
        # or a corrupt DART payload would otherwise surface a raw lxml
        # traceback to the MCP client. Wrap it so callers can recover.
        raise CorpCodeError(f"corp_code index XML is malformed: {exc}") from exc
    entries: list[CorpEntry] = []
    for node in root.findall(".//list"):
        corp_code = (node.findtext("corp_code") or "").strip()
        corp_name = (node.findtext("corp_name") or "").strip()
        stock_code = (node.findtext("stock_code") or "").strip()
        modify_date = (node.findtext("modify_date") or "").strip()
        if not corp_code or not corp_name:
            continue
        entries.append(
            CorpEntry(
                corp_code=corp_code,
                corp_name=corp_name,
                stock_code=stock_code or None,
                modify_date=modify_date,
            )
        )
    return entries


async def ensure_index_loaded(force_refresh: bool = False) -> int:
    """Make sure the in-memory index is populated. Returns # entries."""
    global _INDEX, _BY_NAME, _BY_STOCK, _BY_CORP
    if _INDEX and not force_refresh:
        return len(_INDEX)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if _is_cache_fresh() and not force_refresh:
        xml_bytes = CACHE_FILE.read_bytes()
        logger.info("corp_code: loaded from disk cache")
        try:
            entries = _parse_xml(xml_bytes)
        except CorpCodeError as exc:
            # Corrupt disk cache (e.g. truncated by a partial write) — without
            # this recovery the parse would fail on every call for the full 7
            # day TTL. Discard the bad file and re-download once.
            logger.warning("corp_code: disk cache corrupt (%s), re-downloading", exc)
            CACHE_FILE.unlink(missing_ok=True)
            xml_bytes = await _download_corp_code()
            CACHE_FILE.write_bytes(xml_bytes)
            entries = _parse_xml(xml_bytes)
    else:
        xml_bytes = await _download_corp_code()
        CACHE_FILE.write_bytes(xml_bytes)
        logger.info("corp_code: downloaded fresh from DART (%d bytes)", len(xml_bytes))
        entries = _parse_xml(xml_bytes)

    _INDEX = entries
    _BY_NAME = {e.corp_name: e for e in entries}
    _BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
    _BY_CORP = {e.corp_code: e for e in entries}
    logger.info("corp_code: indexed %d entries", len(entries))
    return len(entries)


async def lookup_by_name(query: str, *, listed_only: bool = False, limit: int = 10) -> list[CorpEntry]:
    """Substring-match `query` against Korean corp names."""
    await ensure_index_loaded()
    q = query.strip()
    if not q:
        return []
    out: list[CorpEntry] = []
    for entry in _INDEX:
        if listed_only and not entry.stock_code:
            continue
        if q in entry.corp_name:
            out.append(entry)
            if len(out) >= limit:
                break
    return out


async def lookup_by_stock_code(stock_code: str) -> Optional[CorpEntry]:
    """Resolve a 6-digit KRX code to its DART entry."""
    await ensure_index_loaded()
    return _BY_STOCK.get(stock_code.strip())


async def lookup_by_corp_code(corp_code: str) -> Optional[CorpEntry]:
    """Resolve an 8-digit DART corp code to its entry."""
    await ensure_index_loaded()
    return _BY_CORP.get(corp_code.strip())
