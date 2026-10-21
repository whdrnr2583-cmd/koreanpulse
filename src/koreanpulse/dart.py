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
import re
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


class DartRateLimited(DartError):
    """Raised when DART itself reports the key's request limit is used up
    (status 020), as opposed to our own soft cap (`DartDailyQuotaExceeded`)."""


class _TransientHttpStatus(Exception):
    """Internal: a retryable HTTP status (429 / 5xx). Never leaves this module."""

    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"transient HTTP {response.status_code}")
        self.response = response


# Base delay for the retry backoff. A module constant so the test suite can
# zero it (tests/conftest.py) instead of sleeping through real backoff.
_RETRY_BASE_SECONDS = 0.5
_RETRY_ATTEMPTS = 3


def _is_transient(exc: BaseException) -> bool:
    """Retry on connection/timeout failures and on 429/5xx responses.

    Deliberately not agentprod's message-pattern matcher: `httpx.ReadTimeout`
    stringifies to "" and `ConnectError` to "connection refused", neither of
    which that matcher recognises, so DART timeouts were never retried.
    """
    return isinstance(exc, (httpx.TransportError, _TransientHttpStatus))


# DART `status` codes worth explaining to a human / LLM. The message DART
# sends is Korean and terse; the hint says what to do about it.
_STATUS_HINTS: dict[str, str] = {
    "010": "The API key is not registered. Check DART_API_KEY (get a free key at "
           "https://opendart.fss.or.kr/; a placeholder from .env.example does not work).",
    "011": "The API key is registered but currently unusable (suspended). "
           "Check its status at https://opendart.fss.or.kr/.",
    "012": "This key is restricted to other IP addresses. Update the allowed IPs "
           "in your DART key settings.",
    "020": "DART's request limit for this key is used up (40,000 calls/day). "
           "It resets at KST midnight; cached queries still work.",
    "021": "Too many companies requested in one query.",
    "100": "A request field has an invalid value (check dates and corp_code).",
    "101": "Access is denied for this request.",
    "800": "DART is under maintenance. Retry later.",
    "900": "DART reported an undefined internal error. Retry later.",
    "901": "The account tied to this API key has expired. Re-issue the key at "
           "https://opendart.fss.or.kr/.",
}


def _raise_for_dart_status(data: dict) -> None:
    """Raise `DartError` for any status other than 000 (ok) / 013 (no data)."""
    status = data.get("status")
    if status in ("000", "013"):
        return
    msg = data.get("message", "unknown DART error")
    hint = _STATUS_HINTS.get(str(status))
    text = f"DART {status}: {msg}" + (f" — {hint}" if hint else "")
    if status == "020":
        raise DartRateLimited(text)
    raise DartError(text)


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
    if key.lower().startswith("your-") or "your-40-char" in key.lower():
        raise DartError(
            "DART_API_KEY is still the placeholder from .env.example. "
            "Replace it with your own key from https://opendart.fss.or.kr/."
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


async def _get_json(
    endpoint: str,
    params: dict,
    *,
    client: Optional[httpx.AsyncClient],
) -> dict:
    """GET `{DART_API_BASE}/{endpoint}` and return the decoded JSON object.

    Shared by every DART endpoint wrapper so retry, quota and error handling
    cannot drift apart. Behaviour:

    - every attempt (including retries) is throttled and counted against the
      soft daily quota, since DART bills each HTTP request;
    - connection errors, timeouts, HTTP 429 and 5xx are retried with
      exponential backoff; other 4xx fail immediately;
    - all failures surface as `DartError` carrying only the status code or
      the exception *type name* — never the request URL, which holds
      `crtfc_key` on its query string;
    - a 200 with a non-JSON body (maintenance page) or a non-object JSON
      value is a `DartError`, not a raw decode error.
    """
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:

        async def _call() -> httpx.Response:
            await _bump_daily_counter(1)
            await _throttle.acquire(timeout=2.0, label=f"dart:{endpoint}")
            resp = await client.get(f"{DART_API_BASE}/{endpoint}", params=params)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise _TransientHttpStatus(resp)
            return resp

        try:
            resp = await retry_async(
                _call,
                max_attempts=_RETRY_ATTEMPTS,
                base_seconds=_RETRY_BASE_SECONDS,
                is_retryable_fn=_is_transient,
            )
            resp.raise_for_status()
        except (_TransientHttpStatus, httpx.HTTPStatusError) as exc:
            code = exc.response.status_code
            raise DartError(
                f"DART {endpoint} returned HTTP {code}. "
                f"This usually means DART is rate-limiting or in maintenance; "
                f"retry shortly."
            ) from exc
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise DartError(
                f"DART {endpoint} request failed after retries: {type(exc).__name__}"
            ) from exc
        # DART normally returns JSON, but on maintenance / gateway errors it
        # can hand back a 200 with an HTML page or an empty body.
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
    return data


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

    data = await _get_json("list.json", params, client=client)
    _raise_for_dart_status(data)
    status = data.get("status")

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

    data = await _get_json("majorstock.json", params, client=client)
    _raise_for_dart_status(data)
    status = data.get("status")

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
    s = str(d).strip().replace("-", "")
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(
            f"invalid date {d!r}: expected YYYY-MM-DD or YYYYMMDD"
        ) from exc


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
    # Exchange fair-disclosure first: "연결재무제표기준영업(잠정)실적(공정공시)" is an
    # I-type disclosure even though its name also contains a periodic-report
    # phrase, and "(공정공시)" never appears in a genuine periodic report title.
    ("공정공시", "I"),
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
    ("최대주주등소유주식변동신고서", "D"),
    ("공개매수", "D"),
    # Exchange disclosure — I
    ("현금ㆍ현물배당결정", "I"),
    ("현금·현물배당결정", "I"),
    ("주주총회소집결의", "I"),
    ("특수관계인", "I"),
    ("특수관계자", "I"),
    ("단일판매", "I"),
    ("공급계약체결", "I"),
    ("투자판단관련주요경영사항", "I"),
    ("조회공시요구", "I"),
    ("매출액또는손익구조", "I"),
    ("주주총회소집공고", "I"),
    ("기업설명회", "I"),
    ("불성실공시법인지정", "I"),
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


# DART writes the Korean interpunct in several code points depending on the
# filer's tooling (U+318D ㆍ, U+00B7 ·, U+2027 ‧, U+30FB ・, U+2022 •). Fold them
# to one so "임원ㆍ주요주주…" and "임원·주요주주…" classify the same way.
_INTERPUNCT_RE = re.compile("[\u00b7\u2027\u2022\u30fb\u318d]")


def _norm_title(title: str) -> str:
    """Whitespace-free, interpunct-folded form used for keyword matching."""
    return _INTERPUNCT_RE.sub("\u318d", "".join(title.split()))


_TITLE_TO_TYPE_NORM: tuple[tuple[str, str], ...] = tuple(
    (_norm_title(prefix), code) for prefix, code in _TITLE_TO_TYPE
)


def _classify_filing_type(title: str) -> str:
    """Heuristic: infer DART filing-type code from the report title.

    Returns one of A/B/C/D/E/F/G/H/I/J. Defaults to E ('other') on no match.
    Matching ignores whitespace and interpunct variants.
    """
    # Strip leading [기재정정] or similar prefixes.
    stripped = _norm_title(_strip_leading_bracket_tags(title))

    for prefix, code in _TITLE_TO_TYPE_NORM:
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
    compact = "".join(title.split())  # "감사의견한정" == "감사의견 한정"
    for keyword, tag in _RED_FLAG_KEYWORDS:
        if "".join(keyword.split()) in compact and tag not in tags:
            tags.append(tag)
    return tags


def _parse_rcept_date(rcept_dt: object, receipt_no: str) -> datetime:
    for candidate in (str(rcept_dt or "").strip(), receipt_no[:8]):
        try:
            return datetime.strptime(candidate, "%Y%m%d")
        except ValueError:
            continue
    logger.warning("dart: no parseable filing date (rcept_dt=%r, rcept_no=%r)", rcept_dt, receipt_no)
    return datetime.now(_KST).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)


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
    title = str(row.get("report_nm") or "").strip()

    # Trust the request param when present, else infer from title.
    filing_type_code = requested_type or _classify_filing_type(title)
    label_ko, label_en = DART_FILING_TYPE_LABELS.get(
        filing_type_code, ("기타공시", "Other")
    )

    # rcept_dt is yyyymmdd
    # rcept_dt is yyyymmdd (KST). If DART omits or garbles it, the first 8
    # digits of the 14-digit receipt number are the same date; only as a last
    # resort fall back to today's KST date, never a UTC "now" that can land on
    # the wrong calendar day.
    filed_at = _parse_rcept_date(row.get("rcept_dt"), receipt_no)

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
