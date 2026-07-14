"""DART (전자공시시스템) OpenAPI client.

DART is the Korean Financial Supervisory Service's electronic disclosure
system. The OpenAPI is free, English-key-supported, and returns JSON for most
list endpoints. Sign up at https://opendart.fss.or.kr/.

## Quotas (verified 2026-05)

- **Daily call limit: 40,000 / API key / day** (DART policy)
- Per-key burst rejected above ~10/s in practice → we throttle at 5/s

## Capacity math

Daily 40K caps the *origin* hits we can serve. Customer-facing call capacity
is roughly `daily_origin / (1 - cache_hit_rate)`:

| Cache hit | Customer calls/day | Customer calls/mo |
|---|---|---|
| 50% (cold)   | 80,000   | 2.4M    |
| 80% (target) | 200,000  | 6M      |
| 90% (mature) | 400,000  | 12M     |

→ Even at 50% hit rate the daily customer ceiling (80K) covers our entire
paid tier mix until well past $5K MRR. Cache is the load-bearing structure.

## Soft daily guard

`DART_DAILY_QUOTA` is a soft cap we enforce *before* sending. Set to 80% of
DART's hard limit so an off-by-one or burst doesn't 0-out the day. Override
with `DART_DAILY_QUOTA` env if you have a higher-quota agreement.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Optional

import httpx

from agentprod import Throttle, retry_async

from koreanpulse.cache import Cache, NullCache, cache_key
from koreanpulse.models import Filing
from koreanpulse.sources import (
    DART_API_BASE,
    DART_ATTRIBUTION,
    DART_FILING_TYPE_LABELS,
)

logger = logging.getLogger(__name__)


class DartError(RuntimeError):
    """Raised when DART returns a non-success status code."""


class DartDailyQuotaExceeded(DartError):
    """Raised when our local soft cap on daily DART calls would be exceeded."""


# DART's published hard cap is 40,000/day per key. Default soft cap = 80% so
# bursts and counter drift never zero out the day. Override via env in prod.
DART_HARD_DAILY_LIMIT = 40_000
_DEFAULT_SOFT_FRACTION = 0.8


def _read_daily_quota() -> int:
    """`DART_DAILY_QUOTA` env override; default 32_000 (80% of 40K)."""
    raw = os.environ.get("DART_DAILY_QUOTA", "").strip()
    if raw:
        try:
            v = int(raw)
            if v > 0:
                return v
        except ValueError:
            pass
    return int(DART_HARD_DAILY_LIMIT * _DEFAULT_SOFT_FRACTION)


# Module-level throttle — single bucket per process / app key.
# 5 req/s burst cap matches DART's empirical per-key burst tolerance.
_throttle = Throttle(capacity=5, refill_per_sec=5, jitter_ms=(10, 50))


# ── Daily counter (KST midnight reset) ─────────────────────────────────────
# DART quota resets at Korea Standard Time midnight (UTC+9). We track calls
# in-process; persist to disk if you run multi-process.
_KST = timezone(timedelta(hours=9))
_daily_lock = asyncio.Lock()
_daily_count = 0
_daily_window_kst = ""  # yyyy-mm-dd in KST


async def _bump_daily_counter(n: int = 1) -> int:
    """Increment counter, raise if soft quota would be exceeded.

    Returns:
        New counter value after increment.

    Raises:
        DartDailyQuotaExceeded: if increment would exceed `DART_DAILY_QUOTA`.
    """
    global _daily_count, _daily_window_kst
    quota = _read_daily_quota()
    today = datetime.now(_KST).date().isoformat()
    async with _daily_lock:
        if today != _daily_window_kst:
            _daily_window_kst = today
            _daily_count = 0
        if _daily_count + n > quota:
            raise DartDailyQuotaExceeded(
                f"DART daily quota would be exceeded "
                f"({_daily_count + n} > {quota}). Window: {today} KST."
            )
        _daily_count += n
        return _daily_count


def daily_usage_snapshot() -> dict:
    """Read-only view of current daily counter — for ops dashboards."""
    return {
        "window_kst": _daily_window_kst,
        "calls": _daily_count,
        "soft_quota": _read_daily_quota(),
        "hard_limit": DART_HARD_DAILY_LIMIT,
    }


def _api_key() -> str:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        raise DartError(
            "DART_API_KEY env var is missing. "
            "Get one at https://opendart.fss.or.kr/ and set it before calling DART tools."
        )
    return key


def _yyyymmdd(d: date | str) -> str:
    if isinstance(d, str):
        # already formatted
        return d.replace("-", "")
    return d.strftime("%Y%m%d")


def _coerce_optional_int(value: object) -> Optional[int]:
    """Best-effort int coercion for a DART numeric-as-string field.

    Returns None (never raises) when `value` is missing or not parseable.
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def list_filings(
    *,
    corp_code: Optional[str] = None,
    bgn_de: date | str,
    end_de: date | str,
    pblntf_ty: Optional[str] = None,  # A/B/C/D/E/F/G/H/I/J
    page_no: int = 1,
    page_count: int = 100,
    client: Optional[httpx.AsyncClient] = None,
) -> list[Filing]:
    """Fetch DART filings list. Thin wrapper around `/list.json`.

    Args:
        corp_code: 8-digit DART corp code. None = all companies.
        bgn_de: start date (yyyymmdd or `date`).
        end_de: end date.
        pblntf_ty: filing type code; see DART_FILING_TYPE_LABELS.
        page_no: 1-indexed.
        page_count: max 100 per DART rules.

    Returns:
        Parsed Filing rows. Empty list if no results.

    Raises:
        DartError: API returned a non-`000` status.
    """
    params = {
        "crtfc_key": _api_key(),
        "bgn_de": _yyyymmdd(bgn_de),
        "end_de": _yyyymmdd(end_de),
        "page_no": str(page_no),
        "page_count": str(min(page_count, 100)),
    }
    if corp_code:
        params["corp_code"] = corp_code
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        # Soft daily-quota guard before throttle — fail fast if we're over budget.
        await _bump_daily_counter(1)
        await _throttle.acquire(timeout=2.0, label="dart:list")

        async def _call() -> httpx.Response:
            return await client.get(f"{DART_API_BASE}/list.json", params=params)

        # A non-2xx status or a network failure that survives all retries
        # otherwise leaks a raw httpx.HTTPStatusError / transport exception to
        # the MCP client. corp_code._download_corp_code wraps the identical
        # failure mode in CorpCodeError — mirror that asymmetry here so both
        # DART entry points hand callers a structured DartError. (No caller
        # depends on the httpx exception type — server.py lets it propagate.)
        try:
            resp = await retry_async(_call, max_attempts=3, base_seconds=0.5)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DartError(
                f"DART list.json returned HTTP {exc.response.status_code}. "
                f"This usually means DART is rate-limiting or in maintenance; "
                f"retry shortly."
            ) from exc
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise DartError(
                f"DART list.json request failed after retries: {exc}"
            ) from exc
        # DART normally returns JSON, but on maintenance / gateway errors it
        # can hand back a 200 with an HTML page or an empty body. `resp.json()`
        # then raises a raw JSONDecodeError that would leak to the MCP client;
        # wrap it in DartError with a clear message instead.
        try:
            data = resp.json()
        except ValueError as exc:
            body_preview = (resp.text or "")[:120].replace("\n", " ")
            raise DartError(
                f"DART returned a non-JSON body (status {resp.status_code}): "
                f"{body_preview!r}. This usually means DART is in maintenance "
                f"or the endpoint returned an error page."
            ) from exc
    finally:
        if owns_client:
            await client.aclose()

    if not isinstance(data, dict):
        raise DartError(f"DART returned an unexpected JSON shape: {type(data).__name__}")

    status = data.get("status")
    if status not in ("000", "013"):
        # 000 = OK, 013 = no result (DART convention). Anything else = error.
        msg = data.get("message", "unknown DART error")
        raise DartError(f"DART {status}: {msg}")

    if status == "013":
        return []

    # `total_count` is DART's full match count for the query before our
    # `page_count`/`limit` truncation — surfaced on each row so a caller
    # can tell "you got N of total_count" without a second request.
    # `data_fetched_at` marks this as a live DART fetch (as opposed to a
    # cache hit replaying a previously-fetched row) — see list_filings_cached.
    query_total_count = _coerce_optional_int(data.get("total_count"))
    fetched_at = datetime.now(timezone.utc)

    filings: list[Filing] = []
    for row in data.get("list", []):
        # A single malformed row (non-dict, or missing the load-bearing
        # `rcept_no` that keys the receipt and DART URL) must not crash the
        # whole request — skip it and keep the good rows. `rcept_no` is
        # normally a 14-digit string, but coerce defensively (e.g. if DART
        # or a proxy ever hands it back as a JSON number) rather than calling
        # `.strip()` on a non-str and leaking a raw AttributeError.
        if not isinstance(row, dict) or not str(row.get("rcept_no") or "").strip():
            logger.warning("dart: skipping malformed filing row: %r", row)
            continue
        filings.append(
            _parse_filing(
                row,
                requested_type=pblntf_ty,
                query_total_count=query_total_count,
                data_fetched_at=fetched_at,
            )
        )
    # Post-process the fetched batch to link each correction re-filing back to
    # the original it amends (no extra DART call — data already in hand).
    _link_corrections(filings)
    return filings


# ── Major shareholding reports (대량보유상황보고) ──────────────────────────
# `/majorstock.json` is a distinct DART endpoint from `/list.json`: it
# returns each reporter's (repror) current holding percentage and its
# change versus the prior report, which the filing-list endpoint doesn't
# carry. Paid-tier enrichment input for `monitor_activist_investors` /
# `monitor_foreign_holders` (see server.py / _enrich.py).

_MAJOR_HOLDING_CACHE_NAMESPACE = "dart_majorstock"
# Majorstock rows are a point-in-time snapshot per corp_code (not a
# date-ranged query), so a flat TTL is enough — 1 hour matches the "recent"
# tier `_ttl_for_query` uses for filings filed in the last week.
_MAJOR_HOLDING_TTL_SECONDS = 3600


@dataclass(frozen=True)
class MajorHolding:
    """One row from DART's majorstock.json (대량보유상황보고).

    Only the 3 fields consumed by the paid-tier enrichment are parsed —
    `repror` (보고자, the reporting entity), `stkrt` (보유비율, current
    holding %), and `stkrt_irds` (증감, change vs the prior report). DART
    returns other fields (report reason, share counts, contract details)
    that we deliberately do not surface here — don't add them without a
    verified live payload to parse against (no fabricated fields).
    """

    repror: str
    stkrt: Optional[float]
    stkrt_irds: Optional[float]


def _coerce_optional_float(value: object) -> Optional[float]:
    """Best-effort float coercion for a DART numeric-as-string field.

    Returns None (never raises) when `value` is missing, empty, or not
    parseable — matching `list_filings`' policy of degrading a single bad
    field rather than crashing the whole response.
    """
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


async def list_major_holdings(
    corp_code: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> list[MajorHolding]:
    """Fetch DART major-shareholding-report rows. Thin wrapper around
    `/majorstock.json`.

    Cached via the shared default cache (see `set_default_cache` /
    `get_default_cache`) for `_MAJOR_HOLDING_TTL_SECONDS` — a cache hit
    consumes no DART quota and does not bump the daily counter.

    Args:
        corp_code: 8-digit DART corp code.
        client: optional shared httpx client.

    Returns:
        Parsed MajorHolding rows (most-recent report order, as DART
        returns them). Empty list when DART has no majorstock report on
        file for this corp (status '013').

    Raises:
        DartError: API returned a non-`000`/`013` status, or the
            request/response failed. Mirrors `list_filings`' error
            handling exactly: an HTTPStatusError surfaces only the status
            code, any other transport failure surfaces only the exception
            type name — never the request URL or `crtfc_key`, which
            `params=` below puts on the query string.
    """
    cache = get_default_cache()
    key = cache_key(_MAJOR_HOLDING_CACHE_NAMESPACE, corp_code)
    cached = await cache.get(key)
    if cached is not None:
        try:
            return [MajorHolding(**item) for item in cached]
        except (TypeError, ValueError) as exc:
            logger.warning("majorstock cache: stale schema, refetching: %s", exc)

    params = {
        "crtfc_key": _api_key(),
        "corp_code": corp_code,
    }

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        # Soft daily-quota guard before throttle — fail fast if we're over budget.
        await _bump_daily_counter(1)
        await _throttle.acquire(timeout=2.0, label="dart:majorstock")

        async def _call() -> httpx.Response:
            return await client.get(f"{DART_API_BASE}/majorstock.json", params=params)

        try:
            resp = await retry_async(_call, max_attempts=3, base_seconds=0.5)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise DartError(
                f"DART majorstock.json returned HTTP {exc.response.status_code}. "
                f"This usually means DART is rate-limiting or in maintenance; "
                f"retry shortly."
            ) from exc
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise DartError(
                f"DART majorstock.json request failed after retries: "
                f"{type(exc).__name__}"
            ) from exc
        try:
            data = resp.json()
        except ValueError as exc:
            body_preview = (resp.text or "")[:120].replace("\n", " ")
            raise DartError(
                f"DART returned a non-JSON body (status {resp.status_code}): "
                f"{body_preview!r}. This usually means DART is in maintenance "
                f"or the endpoint returned an error page."
            ) from exc
    finally:
        if owns_client:
            await client.aclose()

    if not isinstance(data, dict):
        raise DartError(f"DART returned an unexpected JSON shape: {type(data).__name__}")

    status = data.get("status")
    if status not in ("000", "013"):
        # 000 = OK, 013 = no result (DART convention). Anything else = error.
        msg = data.get("message", "unknown DART error")
        raise DartError(f"DART {status}: {msg}")

    holdings: list[MajorHolding] = []
    if status == "000":
        for row in data.get("list", []):
            # A malformed row (non-dict, or missing `repror` — the field
            # both the corp-level match key and the caller's best-match
            # logic key off) must not crash the whole request.
            if not isinstance(row, dict):
                logger.warning("dart: skipping malformed majorstock row: %r", row)
                continue
            repror = str(row.get("repror") or "").strip()
            if not repror:
                logger.warning("dart: skipping majorstock row missing repror: %r", row)
                continue
            holdings.append(
                MajorHolding(
                    repror=repror,
                    stkrt=_coerce_optional_float(row.get("stkrt")),
                    stkrt_irds=_coerce_optional_float(row.get("stkrt_irds")),
                )
            )

    try:
        serialized = [asdict(h) for h in holdings]
        await cache.set(key, serialized, ttl_seconds=_MAJOR_HOLDING_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — cache failure must not block the response
        logger.warning("majorstock cache write failed (suppressed): %s", exc)

    return holdings


# ── Cached filing list ─────────────────────────────────────────────────────
# Filing-list responses are quasi-deterministic per query. Cache aggressively
# with a freshness-aware TTL so the same `(corp, date_range, type)` hit from
# many users only burns one DART quota slot.

_FILING_CACHE_NAMESPACE = "dart_list"


def _ttl_for_query(end_de: date) -> int:
    """Pick a TTL based on how fresh the query window is.

    - end_de is today/future → 60s (new filings could appear any minute)
    - end_de is past 1–6 days ago → 1 hour (recent, may be amended)
    - end_de is past ≥7 days ago → 24 hours (effectively immutable)
    """
    # KST clock — DART filings stamp in KST and the freshness cutoff for
    # "today's window" must follow that, not the caller's local timezone.
    today = datetime.now(timezone(timedelta(hours=9))).date()
    if end_de >= today:
        return 60
    days_old = (today - end_de).days
    if days_old < 7:
        return 3600
    return 86400


def _coerce_date(d: date | str) -> date:
    if isinstance(d, date):
        return d
    s = str(d).replace("-", "")
    return datetime.strptime(s, "%Y%m%d").date()


async def list_filings_cached(
    *,
    cache: Cache,
    corp_code: Optional[str] = None,
    bgn_de: date | str,
    end_de: date | str,
    pblntf_ty: Optional[str] = None,
    page_no: int = 1,
    page_count: int = 100,
    client: Optional[httpx.AsyncClient] = None,
    force_refresh: bool = False,
) -> list[Filing]:
    """Same as `list_filings` but goes through cache first.

    Cache key: SHA256 of the normalized query tuple. TTL depends on `end_de`
    freshness (see `_ttl_for_query`).

    Set `force_refresh=True` to bypass cache (useful for testing or for the
    `koreanpulse refresh` admin path).

    Returns parsed Filing models. On cache hit, *no* DART quota is consumed
    and the daily counter does not increment.
    """
    end_date = _coerce_date(end_de)
    bgn_date = _coerce_date(bgn_de)

    key = cache_key(
        _FILING_CACHE_NAMESPACE,
        corp_code or "_all_",
        bgn_date.isoformat(),
        end_date.isoformat(),
        pblntf_ty or "_all_",
        page_no,
        page_count,
    )

    if not force_refresh:
        cached = await cache.get(key)
        if cached is not None:
            try:
                return [Filing.model_validate(item) for item in cached]
            except (ValueError, TypeError) as exc:
                logger.warning("filing cache: stale schema, refetching: %s", exc)
                # Fall through to live fetch

    filings = await list_filings(
        corp_code=corp_code,
        bgn_de=bgn_date,
        end_de=end_date,
        pblntf_ty=pblntf_ty,
        page_no=page_no,
        page_count=page_count,
        client=client,
    )

    ttl = _ttl_for_query(end_date)
    try:
        serialized = [f.model_dump(mode="json") for f in filings]
        await cache.set(key, serialized, ttl_seconds=ttl)
    except Exception as exc:  # noqa: BLE001 — cache failure must not block the response
        logger.warning("filing cache write failed (suppressed): %s", exc)

    return filings


# Module-level shared cache for the convenience wrapper. Override via
# `set_default_cache()` from server.py so tests / multiple callers share one.
_default_cache: Cache = NullCache()


def set_default_cache(cache: Cache) -> None:
    """Wire the process-wide default cache (call once at startup)."""
    global _default_cache
    _default_cache = cache


def get_default_cache() -> Cache:
    return _default_cache


# Title-prefix heuristics for filing-type classification.
# DART's `list.json` response does NOT include `pblntf_ty` — it's a request-only
# param. So we infer the broad category from the report title. Order matters
# (more specific patterns first).
_TITLE_TO_TYPE: tuple[tuple[str, str], ...] = (
    # Periodic — A
    ("사업보고서", "A"),
    ("반기보고서", "A"),
    ("분기보고서", "A"),
    ("연결재무제표기준영업(잠정)실적", "A"),
    # Major event — B
    ("주요사항보고서", "B"),
    ("자기주식취득결정", "B"),
    ("자기주식처분결정", "B"),
    ("유상증자결정", "B"),
    ("무상증자결정", "B"),
    ("주식분할결정", "B"),
    ("주식병합결정", "B"),
    ("합병결정", "B"),
    ("분할결정", "B"),
    ("영업양도결정", "B"),
    ("영업양수결정", "B"),
    ("자산양수도", "B"),
    ("타법인주식및출자증권취득결정", "B"),
    ("회사합병결정", "B"),
    # Issuance — C
    ("증권발행실적보고서", "C"),
    ("증권신고서", "C"),
    ("투자설명서", "C"),
    ("일괄신고서", "C"),
    # Shareholding — D
    ("주식등의대량보유상황보고서", "D"),
    ("임원ㆍ주요주주특정증권등소유상황보고서", "D"),
    ("임원·주요주주특정증권등소유상황보고서", "D"),
    ("의결권대리행사권유참고서류", "D"),
    # Audit — F
    ("감사보고서", "F"),
    ("외부감사인지정", "F"),
    # Exchange disclosure — I (공정공시 falls here)
    ("공정공시", "I"),
    ("현금ㆍ현물배당결정", "I"),
    ("현금·현물배당결정", "I"),
    ("주주총회소집결의", "I"),
    ("특수관계인", "I"),
    ("특수관계자", "I"),
    # FTC — J
    ("기업집단", "J"),
    ("내부거래", "J"),
)


def _strip_leading_bracket_tags(title: str) -> str:
    """Strip leading DART bracket tags (e.g. [기재정정], [첨부정정]) from a title.

    Only *leading* bracket tags are removed; brackets that appear later in the
    title (rare) are left intact. Used both for filing-type classification and
    for normalizing a correction title back to the original report name.
    """
    stripped = title
    while stripped.startswith("[") and "]" in stripped:
        stripped = stripped[stripped.index("]") + 1 :].lstrip()
    return stripped


def _is_correction_title(title: str) -> bool:
    """True when the title carries a leading DART correction tag.

    DART re-files an amended disclosure with a bracket tag such as [기재정정]
    (content correction) or [첨부정정] (attachment correction) — both contain
    '정정'. Only a leading bracket tag counts; '정정' elsewhere in the report
    name does not flag the filing.
    """
    if not title:
        return False
    remaining = title.lstrip()
    while remaining.startswith("[") and "]" in remaining:
        end = remaining.index("]")
        if "정정" in remaining[1:end]:
            return True
        remaining = remaining[end + 1 :].lstrip()
    return False


def _classify_filing_type(title: str) -> str:
    """Heuristic: infer DART filing-type code from the report title.

    Returns one of A/B/C/D/E/F/G/H/I/J. Defaults to E ('other') on no match.
    """
    # Strip leading [기재정정] or similar prefixes.
    stripped = _strip_leading_bracket_tags(title)

    for prefix, code in _TITLE_TO_TYPE:
        if prefix in stripped:
            return code
    return "E"


# DART `corp_cls` code → listing market. Y=KOSPI, K=KOSDAQ, N=KONEX, E=기타.
# Unknown / absent codes map to None so callers never assert a market DART
# didn't give us.
_CORP_CLS_TO_MARKET: dict[str, str] = {
    "Y": "KOSPI",
    "K": "KOSDAQ",
    "N": "KONEX",
    "E": "OTHER",
}


def market_from_corp_cls(corp_cls: Optional[str]) -> Optional[str]:
    """Map DART's `corp_cls` field to a human market label.

    Returns 'KOSPI' | 'KOSDAQ' | 'KONEX' | 'OTHER', or None when corp_cls is
    absent, empty, or an unrecognized code.
    """
    if not corp_cls:
        return None
    return _CORP_CLS_TO_MARKET.get(str(corp_cls).strip().upper())


# Title-keyword → red-flag tag. Governance / distress signals a reader scans
# a filing feed for. Order defines the tag order in the output list; each tag
# is emitted at most once even if several of its keywords appear.
#
# audit_opinion keywords are distress-only: a clean ('적정') audit opinion
# title must NOT be tagged, since that would flag a healthy company as a red
# flag. '감사의견' alone matches every audit-opinion filing regardless of the
# actual opinion, so it was removed — only the non-clean opinion outcomes
# (의견거절 = disclaimer, 한정 = qualified, 부적정 = adverse) trigger the tag.
# '감사의견 한정' (with the space DART actually uses, e.g.
# "감사보고서(감사의견 한정)") is used instead of a bare '한정' to avoid
# matching unrelated titles that happen to contain that two-character word.
_RED_FLAG_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("전환사채권발행", "cb_issuance"),
    ("최대주주변경", "controlling_shareholder_change"),
    ("회생절차", "rehabilitation"),
    ("의견거절", "audit_opinion"),
    ("감사의견 한정", "audit_opinion"),
    ("부적정", "audit_opinion"),
    ("불성실공시", "disclosure_violation"),
    ("유상증자", "rights_issue"),
    ("감자", "capital_reduction"),
    # Added 2026-07-12 — broaden distress/governance coverage beyond the
    # original 9 keywords.
    ("관리종목", "management_designation"),
    ("상장폐지", "delisting_risk"),
    ("거래정지", "trading_halt"),
    ("주식병합", "reverse_split"),
    ("단기차입금", "short_term_borrowing"),
    ("계속기업", "going_concern"),
    ("존속능력", "going_concern"),
)


def tag_red_flags(title: str) -> list[str]:
    """Pure function: filing title → ordered list of red-flag tags.

    Keyword-based; no external state. Returns [] on no match. A tag appears
    at most once even when multiple of its trigger keywords are present
    (e.g. both '의견거절' and '감사의견 한정' yield a single 'audit_opinion').
    A clean audit opinion (e.g. '감사보고서(감사의견 적정)') is intentionally
    not tagged — only distress outcomes (disclaimer/qualified/adverse) are.
    """
    if not title:
        return []
    tags: list[str] = []
    for keyword, tag in _RED_FLAG_KEYWORDS:
        if keyword in title and tag not in tags:
            tags.append(tag)
    return tags


def _parse_filing(
    row: dict,
    *,
    requested_type: Optional[str] = None,
    query_total_count: Optional[int] = None,
    data_fetched_at: Optional[datetime] = None,
) -> Filing:
    """Convert one DART row dict into a Filing model.

    Args:
        row: DART list.json item.
        requested_type: if the caller filtered the list by `pblntf_ty`, pass it
            through so we trust the request over the title heuristic.
        query_total_count: DART's `total_count` for the query this row came
            from — threaded through unchanged from `list_filings`, not
            re-derived per row.
        data_fetched_at: UTC timestamp of the live DART fetch. Omitted (None)
            for rows reconstructed from a cache entry — see
            `list_filings_cached`, which round-trips through
            `Filing.model_dump`/`model_validate` instead of this function.
    """
    receipt_no = str(row.get("rcept_no") or "").strip()
    title = row.get("report_nm", "").strip()

    # Trust the request param when present, else infer from title.
    filing_type_code = requested_type or _classify_filing_type(title)
    label_ko, label_en = DART_FILING_TYPE_LABELS.get(
        filing_type_code, ("기타공시", "Other")
    )

    # rcept_dt is yyyymmdd
    rcept_dt = row.get("rcept_dt", "")
    try:
        filed_at = datetime.strptime(rcept_dt, "%Y%m%d")
    except ValueError:
        filed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    return Filing(
        corp_code=row.get("corp_code", ""),
        corp_name_ko=row.get("corp_name", ""),
        stock_code=row.get("stock_code") or None,
        market=market_from_corp_cls(row.get("corp_cls")),
        red_flags=tag_red_flags(title),
        filing_type=filing_type_code,
        filing_type_label_ko=label_ko,
        filing_type_label_en=label_en,
        title=title,
        is_correction=_is_correction_title(title),
        receipt_no=receipt_no,
        filed_at=filed_at,
        dart_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}",
        filer_name_ko=(row.get("flr_nm") or "").strip() or None,
        attribution=DART_ATTRIBUTION,
        query_total_count=query_total_count,
        data_fetched_at=data_fetched_at,
    )


def _receipt_lt(a: str, b: str) -> bool:
    """True when receipt number `a` is strictly earlier than `b`.

    DART receipt numbers are 14-digit `yyyymmdd` + 6-digit sequence, so they
    order monotonically (and disambiguate same-day filings, which a date-only
    compare cannot). Compare numerically when both are digit strings, else
    fall back to a lexicographic compare so a malformed value never raises.
    """
    if a.isdigit() and b.isdigit():
        return int(a) < int(b)
    return a < b


def _link_corrections(filings: list[Filing]) -> None:
    """Resolve `previous_receipt_no` on correction filings, in place.

    Post-processing only — operates on the batch already fetched, issues no
    new DART call and does not widen the window. For each `is_correction`
    filing, find the closest PRIOR filing in the same batch with the same
    corp_code, an exact normalized report name (leading bracket tags
    stripped), and an earlier receipt number. When several qualify, link the
    latest one still earlier than the correction (the immediately preceding
    version). Leaves `previous_receipt_no=None` when no confident match exists
    in the window — a wrong link is worse than no link.
    """
    by_key: dict[tuple[str, str], list[Filing]] = {}
    for f in filings:
        norm = _strip_leading_bracket_tags(f.title).strip()
        by_key.setdefault((f.corp_code, norm), []).append(f)

    for f in filings:
        if not f.is_correction or not f.corp_code:
            # Empty corp_code can't be matched safely (unrelated corps would
            # collide on report name alone) — leave it unlinked.
            continue
        norm = _strip_leading_bracket_tags(f.title).strip()
        prior = [
            c
            for c in by_key.get((f.corp_code, norm), [])
            if c is not f and _receipt_lt(c.receipt_no, f.receipt_no)
        ]
        if not prior:
            continue
        best = max(
            prior,
            key=lambda c: int(c.receipt_no) if c.receipt_no.isdigit() else -1,
        )
        f.previous_receipt_no = best.receipt_no
