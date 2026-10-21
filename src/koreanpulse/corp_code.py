"""DART corp-code resolver.

DART identifies companies by an 8-digit `corp_code`, distinct from the KRX
6-digit stock_code. The mapping lives in a single XML file (~5MB) downloaded
from `corpCode.xml`. We download once, parse, build an in-memory index, and
serve name → corp_code lookups instantly.

Refresh policy: cache the file to disk for 7 days. Companies rarely move corp
codes, so this is plenty fresh.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import tempfile
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from lxml import etree

from koreanpulse._paths import data_dir

logger = logging.getLogger(__name__)


CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
CACHE_DIR = data_dir() / "dart"
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
# Normalized names, parallel to _INDEX (rebuilt lazily when the lengths differ).
_NORM_NAMES: list[str] = []
# time.time() of the last successful (re)load; 0.0 = unknown (index seeded by hand).
_LOADED_AT = 0.0
_load_lock: Optional[asyncio.Lock] = None
_load_lock_loop: Optional[asyncio.AbstractEventLoop] = None


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
    except httpx.HTTPStatusError as exc:
        # httpx.HTTPStatusError's message interpolates the *request URL*,
        # which includes crtfc_key on the query string (params= above) — a
        # raw f"{exc}" here would leak DART_API_KEY into the MCP tool error
        # text on any non-2xx response. Mirror dart.py's pattern: only the
        # status code, never the exception object itself.
        raise CorpCodeError(
            f"corp_code index download failed: HTTP {exc.response.status_code}"
        ) from exc
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        # Other httpx errors (connect/read/pool timeouts, transport errors)
        # don't carry the request URL in their message, so the exception
        # type name is safe to surface without risking a key leak.
        raise CorpCodeError(
            f"corp_code index download failed: {type(exc).__name__}"
        ) from exc

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
    """Parse the corp index XML in a streaming pass.

    `iterparse` + clearing each `<list>` after use keeps the lxml tree out of
    memory (the full DOM of the ~24 MB file was built and held until return)
    and walks each record's children once instead of four `findtext` path
    lookups per record.
    """
    entries: list[CorpEntry] = []
    try:
        for _, node in etree.iterparse(io.BytesIO(xml_bytes), events=("end",), tag="list"):
            fields = {"corp_code": "", "corp_name": "", "stock_code": "", "modify_date": ""}
            for child in node:
                if child.tag in fields and child.text:
                    fields[child.tag] = child.text.strip()
            node.clear()
            while node.getprevious() is not None:
                del node.getparent()[0]
            if not fields["corp_code"] or not fields["corp_name"]:
                continue
            entries.append(
                CorpEntry(
                    corp_code=fields["corp_code"],
                    corp_name=fields["corp_name"],
                    stock_code=fields["stock_code"] or None,
                    modify_date=fields["modify_date"],
                )
            )
    except etree.XMLSyntaxError as exc:
        # A truncated disk cache (partial write on disk-full / killed process)
        # or a corrupt DART payload would otherwise surface a raw lxml
        # traceback to the MCP client. Wrap it so callers can recover.
        raise CorpCodeError(f"corp_code index XML is malformed: {exc}") from exc
    return entries


def _get_load_lock() -> asyncio.Lock:
    """One lock per running event loop, so concurrent first calls trigger a
    single download instead of N parallel ~5 MB fetches."""
    global _load_lock, _load_lock_loop
    loop = asyncio.get_running_loop()
    if _load_lock is None or _load_lock_loop is not loop:
        _load_lock = asyncio.Lock()
        _load_lock_loop = loop
    return _load_lock


def _memory_index_stale() -> bool:
    """True when a long-running server's in-memory index is older than the TTL.

    Without this the index was loaded once per process and never refreshed,
    so a stdio server left running for weeks never saw new listings (IPOs)
    or renamed companies until restarted.
    """
    return bool(_LOADED_AT) and (time.time() - _LOADED_AT) > CACHE_TTL_SECONDS


def _write_cache_atomically(xml_bytes: bytes) -> None:
    """Best-effort atomic write: a crash mid-write must not leave a truncated
    file that then looks 'fresh' for seven days. A cache that cannot be
    written degrades to re-downloading, not to an error."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, prefix="corpCode.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(xml_bytes)
            os.replace(tmp, CACHE_FILE)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError as exc:
        logger.warning("corp_code: could not write disk cache (%s); continuing without it", exc)


def _install(entries: list[CorpEntry]) -> None:
    global _INDEX, _BY_NAME, _BY_STOCK, _BY_CORP, _NORM_NAMES, _LOADED_AT
    _INDEX = entries
    _BY_NAME = {e.corp_name: e for e in entries}
    _BY_STOCK = {e.stock_code: e for e in entries if e.stock_code}
    _BY_CORP = {e.corp_code: e for e in entries}
    _NORM_NAMES = [_norm_name(e.corp_name) for e in entries]
    _LOADED_AT = time.time()
    logger.info("corp_code: indexed %d entries", len(entries))


async def ensure_index_loaded(force_refresh: bool = False) -> int:
    """Make sure the in-memory index is populated. Returns # entries.

    Refresh policy: disk cache for 7 days, and the in-memory index is also
    re-read after 7 days in a long-running process. If a refresh download
    fails but an older index (memory or disk) exists, the older one is kept
    and a warning is logged — a transient DART outage must not take
    company-name lookups down with it.
    """
    if _INDEX and not force_refresh and not _memory_index_stale():
        return len(_INDEX)

    async with _get_load_lock():
        # Another caller may have finished the load while we waited.
        if _INDEX and not force_refresh and not _memory_index_stale():
            return len(_INDEX)

        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("corp_code: cache dir %s unusable (%s)", CACHE_DIR, exc)

        entries: Optional[list[CorpEntry]] = None
        if not force_refresh and _is_cache_fresh():
            try:
                entries = _parse_xml(CACHE_FILE.read_bytes())
                logger.info("corp_code: loaded from disk cache")
            except (CorpCodeError, OSError) as exc:
                # Corrupt/truncated disk cache: discard it so the download
                # below replaces it instead of failing for the full TTL.
                logger.warning("corp_code: disk cache unusable (%s), re-downloading", exc)
                CACHE_FILE.unlink(missing_ok=True)

        if entries is None:
            try:
                xml_bytes = await _download_corp_code()
                entries = _parse_xml(xml_bytes)
            except CorpCodeError as exc:
                entries = _fallback_entries(exc)
            else:
                _write_cache_atomically(xml_bytes)
                logger.info("corp_code: downloaded fresh from DART (%d bytes)", len(xml_bytes))

        _install(entries)
        return len(entries)


def _fallback_entries(exc: CorpCodeError) -> list[CorpEntry]:
    """Pick the best older index when a (re)download failed, else re-raise."""
    if _INDEX:
        logger.warning("corp_code: refresh failed (%s); keeping the in-memory index", exc)
        return _INDEX
    if CACHE_FILE.exists():
        try:
            entries = _parse_xml(CACHE_FILE.read_bytes())
        except (CorpCodeError, OSError):
            raise exc
        logger.warning("corp_code: refresh failed (%s); using the stale disk cache", exc)
        return entries
    raise exc


# ── Name normalization + English aliases ───────────────────────────────────

_NON_WORD_RE = re.compile(r"[\W_]+")


def _norm_name(text: str) -> str:
    """Case-, width-, spacing- and punctuation-insensitive form of a company
    name. "(주)" / "주식회사" markers are dropped so "SK 하이닉스",
    "sk하이닉스" and "㈜SK하이닉스" all compare equal."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = t.replace("(주)", "").replace("주식회사", "")
    return _NON_WORD_RE.sub("", t)


# English / romanized name -> the name DART actually lists. DART's index is
# Korean-only, so an English-first agent searching "Samsung Electronics" got
# an empty list. Only well-known listed groups are mapped, and only the
# Korean target is used: results always come from the real DART index.
_ENGLISH_ALIASES: dict[str, tuple[str, ...]] = {
    "samsung electronics": ("삼성전자",),
    "samsung sdi": ("삼성SDI",),
    "samsung biologics": ("삼성바이오로직스",),
    "samsung c&t": ("삼성물산",),
    "samsung life": ("삼성생명",),
    "samsung heavy industries": ("삼성중공업",),
    "samsung electro-mechanics": ("삼성전기",),
    "sk hynix": ("SK하이닉스",),
    "sk innovation": ("SK이노베이션",),
    "sk telecom": ("SK텔레콤",),
    "sk square": ("SK스퀘어",),
    "lg energy solution": ("LG에너지솔루션",),
    "lg chem": ("LG화학",),
    "lg electronics": ("LG전자",),
    "hyundai motor": ("현대자동차",),
    "hyundai mobis": ("현대모비스",),
    "hyundai rotem": ("현대로템",),
    "hd hyundai heavy industries": ("HD현대중공업",),
    "kia": ("기아",),
    "hanwha aerospace": ("한화에어로스페이스",),
    "posco holdings": ("POSCO홀딩스",),
    "naver": ("NAVER",),
    "kakao": ("카카오",),
    "celltrion": ("셀트리온",),
    "kb financial": ("KB금융",),
    "shinhan financial": ("신한지주",),
    "hana financial": ("하나금융지주",),
    "korean air": ("대한항공",),
    "krafton": ("크래프톤",),
    "ncsoft": ("엔씨소프트",),
    "alteogen": ("알테오젠",),
    "ecopro": ("에코프로",),
    "doosan enerbility": ("두산에너빌리티",),
    "kt&g": ("KT&G",),
}
_ENGLISH_ALIASES_NORM: dict[str, tuple[str, ...]] = {
    _norm_name(k): v for k, v in _ENGLISH_ALIASES.items()
}


def english_alias_targets(query: str) -> tuple[str, ...]:
    """Korean DART names suggested for an English/romanized `query`
    (exact or partial match on a well-known name); () when none."""
    q = _norm_name(query)
    if len(q) < 3:
        return ()
    out: list[str] = []
    for key, targets in _ENGLISH_ALIASES_NORM.items():
        if q == key or (len(q) >= 4 and q in key):
            out.extend(t for t in targets if t not in out)
    return tuple(out)


async def lookup_by_name(query: str, *, listed_only: bool = False, limit: int = 10) -> list[CorpEntry]:
    """Substring-match `query` against Korean corp names.

    Matching ignores case, width, spaces/punctuation and "(주)" markers, and a
    well-known English name ("Samsung Electronics", "SK hynix") is mapped to
    its DART Korean name first (see `_ENGLISH_ALIASES`).

    Collects *all* matches (respecting `listed_only`) before ranking, then
    sorts so the most useful hit lands first — an early-break on `limit`
    during the scan would silently drop a better match that happens to sit
    later in the raw index (e.g. a real ticker's exact name being outranked
    by an unrelated "XXX서비스" subsidiary that appears earlier). Sort key,
    ascending on every field:
        1. exact name match first
        2. prefix match first
        3. listed (stock_code set) before unlisted
        4. shorter corp_name first
        5. most recently modified first
    """
    await ensure_index_loaded()
    q = query.strip()
    if not q:
        return []
    targets = [t for t in {_norm_name(q), *(_norm_name(a) for a in english_alias_targets(q))} if t]
    if not targets:
        return []
    if len(_NORM_NAMES) != len(_INDEX):
        _rebuild_norm_names()
    matches = [
        (entry, norm)
        for entry, norm in zip(_INDEX, _NORM_NAMES)
        if any(t in norm for t in targets) and (not listed_only or entry.stock_code)
    ]

    def _modify_rank(entry: CorpEntry) -> int:
        # Descending modify_date via negation (sort() is ascending only).
        # Falls back to 0 for a missing/non-numeric modify_date rather than
        # raising, since DART occasionally omits it.
        try:
            return -int(entry.modify_date)
        except (TypeError, ValueError):
            return 0

    matches.sort(
        key=lambda m: (
            m[1] not in targets,
            not any(m[1].startswith(t) for t in targets),
            m[0].stock_code is None,
            len(m[0].corp_name),
            _modify_rank(m[0]),
        )
    )
    return [entry for entry, _ in matches[: max(0, limit)]]


def _rebuild_norm_names() -> None:
    global _NORM_NAMES
    _NORM_NAMES = [_norm_name(e.corp_name) for e in _INDEX]


def normalize_stock_code(stock_code: str) -> str:
    """Normalize an upstream ticker string to DART's 6-digit format.

    Strips whitespace, uppercases, drops a trailing exchange suffix (`.KS`
    / `.KQ` / `.KRX`), and left-pads with zeros when what remains is
    all-digit and shorter than 6 characters — many upstream feeds drop the
    leading zero (e.g. "5930" for Samsung Electronics' "005930"). Pure
    string transform — does not touch the index, so it's safe to call
    outside `lookup_by_stock_code` (e.g. to derive a candidate code before
    looking it up, as `server.resolve_stock_code`'s preferred-stock hint
    does).
    """
    code = stock_code.strip().upper()
    for suffix in (".KS", ".KQ", ".KRX"):
        if code.endswith(suffix):
            code = code[: -len(suffix)]
            break
    if code.isdigit() and len(code) < 6:
        code = code.zfill(6)
    return code


async def lookup_by_stock_code(stock_code: str) -> Optional[CorpEntry]:
    """Resolve a 6-digit KRX code to its DART entry.

    See `normalize_stock_code` for the format normalization applied before
    the lookup.
    """
    await ensure_index_loaded()
    return _BY_STOCK.get(normalize_stock_code(stock_code))


async def lookup_by_corp_code(corp_code: str) -> Optional[CorpEntry]:
    """Resolve an 8-digit DART corp code to its entry."""
    await ensure_index_loaded()
    return _BY_CORP.get(corp_code.strip())
