"""koreanpulse MCP server entry point.

Wires the FastMCP server with all currently shipped tools. Run with:

    DART_API_KEY=...           # required
    ANTHROPIC_API_KEY=...      # required if you want server-side translation
    KOREANPULSE_REQUIRE_LICENSE=1   # optional, off by default in dev
    koreanpulse

Or import `mcp` and mount it inside another FastMCP app.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional

from agentprod import CostTracker
from fastmcp import FastMCP

from koreanpulse import __version__
from koreanpulse._enrich import fill_corp_name_en, fill_holding_pct
from koreanpulse._paths import data_dir
from koreanpulse.activists import (
    FOREIGN_HOLDERS,
    KOREAN_ACTIVISTS,
    match_activist,
    match_foreign_holder,
)
from koreanpulse.cache import FileCache
from koreanpulse.corp_code import (
    CorpEntry,
    ensure_index_loaded,
    lookup_by_name,
    lookup_by_stock_code,
    normalize_stock_code,
)
from koreanpulse.dart import list_filings_cached, set_default_cache as _set_dart_cache
from koreanpulse.license import (
    POSTGRES_REMOVED_MESSAGE,
    LicenseError,
    validate_license_or_raise,
)
from koreanpulse.models import ActivistFiling, Article, Filing, ForeignHolderFiling
from koreanpulse.news import INDUSTRY_KEYWORDS, fetch_industry_news
from koreanpulse.sources import NEWS_SOURCE_BY_KEY
from koreanpulse.translate import Translator

# DART filings are stamped in KST (UTC+9). When a US/EU user asks for
# "today" or "last 7 days" the window must follow DART's clock, not the
# caller's local one — otherwise we'd show empty/stale windows for half
# the planet.
_KST = timezone(timedelta(hours=9))


def _kst_today() -> date:
    return datetime.now(_KST).date()


def _parse_since(raw: str) -> datetime:
    """Parse an ISO-8601 `since` cutoff into a naive KST-wall-clock datetime.

    `Filing.filed_at` is a *naive* datetime derived from DART's `rcept_dt`
    (yyyymmdd, stamped in KST) — i.e. the filing date at KST midnight with
    no tzinfo. To compare against it without a tz mismatch, we normalize the
    caller's `since` to the same footing: a tz-aware input is converted to
    KST wall-clock then stripped of tzinfo; a naive input is assumed to
    already be KST. Note `filed_at` is date-granular (always midnight), so a
    `since` with a time component filters at day boundaries in practice.

    Raises ValueError on a malformed string rather than silently ignoring it.
    """
    s = raw.strip()
    if s[-1:] in ("Z", "z"):  # Python 3.10 fromisoformat can't parse 'Z'
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(
            "track_korean_filings: `since` must be an ISO-8601 date or "
            "datetime (e.g. '2026-05-01' or '2026-05-01T09:00:00'); "
            f"got {raw!r}"
        ) from exc
    if dt.tzinfo is not None:
        dt = dt.astimezone(_KST).replace(tzinfo=None)
    return dt


logger = logging.getLogger(__name__)

mcp = FastMCP("koreanpulse")

# Singletons reused across tool invocations.
_cache = FileCache(root=data_dir() / "cache")
_cost_tracker = CostTracker(jsonl_path=str(data_dir() / "cost.jsonl"))
_translator: Optional[Translator] = None

# Wire the shared cache into the DART module so the cached filings wrapper
# can pull from the same backing store as translations.
_set_dart_cache(_cache)


def _get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator(cache=_cache, cost_tracker=_cost_tracker)
    return _translator


# Bounded fan-out for title translation. 8 concurrent short (~50-token)
# requests stays far under OpenAI tier-1 limits (500 RPM / 200k TPM for
# gpt-5-mini-class models) and is trivial load for the hosted cache-worker.
# A sequential loop was measured at 117.5s for a cold-cache 10-company
# batch (147 rows) — past every common MCP client timeout.
_TRANSLATE_CONCURRENCY = 8


async def _fill_title_en(
    filings: list,
    translator: Translator,
    *,
    tool: str,
    text_attr: str = "title",
) -> int:
    """Fill `title_en` on rows concurrently, deduping identical titles.

    Identical titles (common: many filings share the same DART report name)
    are translated exactly once per call, so the cache never sees duplicate
    in-flight misses. A failed translation logs a warning and leaves that
    row's `title_en` unset — the row itself is always kept, with the Korean
    text still present (same fallback as the old sequential loop).

    `text_attr` names the Korean source field (`title` for filings,
    `title_ko` for news articles).

    Returns the number of rows left untranslated because of a failure, so the
    caller can tell the agent instead of leaving a silent gap.
    """
    pending: dict[str, list] = {}
    for f in filings:
        text = getattr(f, text_attr, "")
        if not f.title_en and text:
            pending.setdefault(text, []).append(f)
    if not pending:
        return 0

    sem = asyncio.Semaphore(_TRANSLATE_CONCURRENCY)
    failed_rows = 0

    async def _one(title: str) -> None:
        nonlocal failed_rows
        async with sem:
            try:
                out = await translator.translate_ko_to_en(title, labels={"tool": tool})
            except Exception as exc:  # noqa: BLE001
                group = pending[title]
                failed_rows += len(group)
                logger.warning(
                    "translate failed for %s (%d row(s)): %s",
                    getattr(group[0], "receipt_no", None) or getattr(group[0], "url", "?"),
                    len(group), exc,
                )
                return
        for f in pending[title]:
            f.title_en = out

    await asyncio.gather(*(_one(t) for t in pending))
    return failed_rows


def _translation_unavailable(translator: Translator) -> bool:
    """True when no translation backend is configured (no provider key /
    license key), so attempting it would only produce N identical errors."""
    return getattr(translator, "configured", True) is False


async def _translate_rows(
    rows: list,
    notes: list[str],
    *,
    tool: str,
    text_attr: str = "title",
    corp_names: bool = True,
) -> None:
    """Translate titles (+ company names) for `rows`, recording on `notes`
    anything the caller should know: no backend configured, or a partial
    failure. Never raises."""
    if not rows:
        return
    translator = _get_translator()
    if _translation_unavailable(translator):
        notes.append(
            "translate=true was requested but no translation backend is configured "
            "(set OPENAI_API_KEY, or ANTHROPIC_API_KEY with "
            "KOREANPULSE_TRANSLATE_PROVIDER=anthropic). `title_en` is empty; "
            "the Korean text is unchanged."
        )
        return
    failed = await _fill_title_en(rows, translator, tool=tool, text_attr=text_attr)
    if failed:
        notes.append(
            f"{failed} of {len(rows)} titles could not be translated (provider error); "
            "their `title_en` is empty and the Korean text is unchanged."
        )
    if corp_names:
        await fill_corp_name_en(rows, translator, op=tool)


# ── Input validation + result envelope ─────────────────────────────────────

_CORP_CODE_RE = re.compile(r"^\d{8}$")
_FILING_TYPES = "ABCDEFGHIJ"
_MAX_SCAN_PAGES_DEFAULT = 10
_DART_PAGE_SIZE = 100


def _check_corp_code(value: str, *, tool: str, arg: str) -> str:
    """Return a clean 8-digit corp_code or raise a ValueError that tells the
    caller which tool turns what they have into one."""
    v = str(value).strip()
    if _CORP_CODE_RE.match(v):
        return v
    if v.isdigit() and len(v) == 6:
        hint = "that looks like a 6-digit KRX stock code; call `resolve_stock_code` to get the corp_code"
    elif any(ch.isalpha() for ch in v):
        hint = "that looks like a company name; call `lookup_corp_code` to get the corp_code"
    else:
        hint = "corp_code is always exactly 8 digits (DART's id, not the KRX ticker); call `lookup_corp_code` or `resolve_stock_code`"
    raise ValueError(f"{tool}: `{arg}` must be an 8-digit DART corp_code such as '00126380'; got {v!r} — {hint}.")


def _check_filing_type(value: Optional[str], *, tool: str) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    v = str(value).strip().upper()
    if len(v) == 1 and v in _FILING_TYPES:
        return v
    raise ValueError(
        f"{tool}: `filing_type` must be one letter A-J "
        "(A=periodic, B=major event, C=issuance, D=shareholding, E=other, F=audit, "
        f"G=fund, H=ABS, I=exchange, J=FTC); got {value!r}."
    )


def _clamp(value: int, lo: int, hi: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(v, hi))


def _max_scan_pages() -> int:
    try:
        n = int(os.environ.get("KOREANPULSE_MAX_SCAN_PAGES", "") or _MAX_SCAN_PAGES_DEFAULT)
    except ValueError:
        n = _MAX_SCAN_PAGES_DEFAULT
    return max(1, min(n, 50))


def _window(bgn: date, end: date) -> dict[str, str]:
    return {"from": bgn.isoformat(), "to": end.isoformat()}


def _envelope(rows: list, notes: list[str], *, window: dict[str, str], **extra: Any) -> Any:
    """Bare list when there is nothing to explain (the long-standing shape);
    otherwise `{"filings": [...], "notes": [...], "window_kst": {...}}`.

    An empty list tells an agent nothing: was the window too narrow, the
    company wrong, the scan cut short? Whenever the result is empty,
    truncated, incomplete or degraded, the notes say which.
    """
    if not notes and rows:
        return rows
    out: dict[str, Any] = {"filings": rows, "window_kst": window, "notes": notes}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


@dataclass
class _Scan:
    rows: list
    total: Optional[int]      # DART's total_count for the unfiltered query
    examined: int             # rows actually inspected
    exhausted: bool           # True when every DART row in the window was inspected
    more: bool = False        # True when more matches exist beyond `rows`


async def _list_page(
    *,
    corp_code: Optional[str],
    bgn_de: date,
    end_de: date,
    pblntf_ty: Optional[str],
    page: int,
    page_count: int,
) -> list:
    kwargs: dict[str, Any] = dict(
        cache=_cache,
        corp_code=corp_code,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty=pblntf_ty,
        page_count=page_count,
    )
    if page > 1:  # page 1 is DART's default; keep the call identical to the legacy one
        kwargs["page_no"] = page
    return await list_filings_cached(**kwargs)


async def _scan_filings(
    *,
    corp_code: Optional[str],
    bgn_de: date,
    end_de: date,
    pblntf_ty: Optional[str],
    limit: int,
    page: int = 1,
    predicate: Optional[Callable[[Any], bool]] = None,
) -> _Scan:
    """Fetch filings, applying a client-side `predicate` correctly.

    Without a predicate this is one DART page of `limit` rows (`page`-th).

    With a predicate (allowlist match, red flags, ...) the DART page must NOT
    be sized by `limit`: DART returns the newest N rows of *all* filings, and
    filtering those N afterwards silently drops every older match — e.g. a
    14-day all-company shareholding query returns hundreds of rows per day, so
    `limit=50` examined about half a day and reported "no activist" for the
    rest. Instead pages of 100 are read newest-first until `page * limit + 1`
    matches are found or the window is exhausted, capped at
    KOREANPULSE_MAX_SCAN_PAGES pages (default 10) to bound DART quota use.
    """
    if predicate is None:
        rows = (
            await _list_page(
                corp_code=corp_code, bgn_de=bgn_de, end_de=end_de, pblntf_ty=pblntf_ty,
                page=page, page_count=limit,
            )
        )[:limit]
        total = next((r.query_total_count for r in rows if r.query_total_count is not None), None)
        # DART always reports total_count; it is only unknown for rows cached
        # before that field existed, in which case we cannot claim "more".
        exhausted = True if total is None else page * limit >= total
        return _Scan(rows, total, len(rows), exhausted, more=not exhausted)

    want = page * limit + 1
    max_pages = _max_scan_pages()
    matches: list = []
    examined = 0
    total: Optional[int] = None
    exhausted = False
    for pg in range(1, max_pages + 1):
        batch = await _list_page(
            corp_code=corp_code, bgn_de=bgn_de, end_de=end_de, pblntf_ty=pblntf_ty,
            page=pg, page_count=_DART_PAGE_SIZE,
        )
        if total is None:
            total = next((r.query_total_count for r in batch if r.query_total_count is not None), None)
        examined += len(batch)
        matches.extend(r for r in batch if predicate(r))
        if len(batch) < _DART_PAGE_SIZE or (total is not None and examined >= total):
            exhausted = True
            break
        if len(matches) >= want:
            break
    start = (page - 1) * limit
    return _Scan(
        matches[start:start + limit], total, examined, exhausted,
        more=len(matches) > page * limit,
    )


def _scan_notes(scan: _Scan, *, what: str, bgn: date, end: date, page: int, hint: str) -> list[str]:
    """Human/LLM-readable caveats for a scan: empty, cut short, or truncated."""
    notes: list[str] = []
    if not scan.exhausted and scan.rows is not None and scan.total is not None and scan.examined < scan.total:
        notes.append(
            f"INCOMPLETE SCAN: inspected the newest {scan.examined} of {scan.total} DART filings in "
            f"{bgn}..{end} (KST) before hitting the scan cap, so older filings were not checked and "
            f"the absence of a match is not conclusive. Narrow `days` or pass `company_corp_code`."
        )
    if scan.more:
        notes.append(f"More {what} exist beyond this page; call again with page={page + 1}.")
    if not scan.rows:
        notes.append(
            f"No {what} found in {bgn}..{end} (KST)"
            + (" among the filings inspected" if not scan.exhausted else "")
            + f". {hint}"
        )
    return notes


def _require_license() -> bool:
    """Toggle license gate via env. Off in dev, on in prod."""
    return os.environ.get("KOREANPULSE_REQUIRE_LICENSE", "0").strip() == "1"


async def _gate(license_key: Optional[str], *, units: int = 1) -> None:
    """Free-tier gate — only enforces when KOREANPULSE_REQUIRE_LICENSE=1.

    Used by tools that ship in the free tier (DART filings, corp lookup,
    industry news, server info). On the hosted endpoint (env=0), free-tier
    tools answer without any license check.
    """
    if not _require_license():
        return
    try:
        await validate_license_or_raise(license_key, cost_units=units)
    except LicenseError as exc:
        # Surface a clean, actionable error to the LLM client.
        raise RuntimeError(f"[koreanpulse:{exc.code}] {exc}") from exc


async def _paid_gate(
    license_key: Optional[str],
    *,
    units: int = 1,
    tool_name: str = "",
) -> Optional[str]:
    """Always-on gate for paid-tier tools.

    Returns ``None`` when the license is valid; the caller proceeds normally.
    Returns a paywall message string when the license is missing or invalid;
    the caller MUST return that string immediately so it reaches the user as
    a regular tool result.

    Why a string instead of ``raise``: a raised RuntimeError gets serialized
    by FastMCP as an MCP error (``isError=true``), and several LLM clients
    (notably ChatGPT's mcp connector) treat that as an internal failure and
    never forward the license-required notice to the user. Returning a
    normal string forces the message through the success path so the LLM
    hands it to the user verbatim.
    """
    try:
        await validate_license_or_raise(license_key, cost_units=units)
        return None
    except LicenseError:
        return (
            f"`{tool_name}` requires a license key. Pass a `license_key` "
            f"argument when calling this tool. The activist/foreign-holder "
            f"allowlist tagging runs server-side on the hosted koreanpulse service. "
            f"OSS self-host (github.com/whdrnr2583-cmd/koreanpulse + your own "
            f"DART API key) is free but does NOT include this allowlist tagging, so "
            f"self-hosting will not unlock this tool."
        )


# `fill_corp_name_en` lives in `koreanpulse._enrich` so it can be
# unit-tested without importing FastMCP. The server module just calls it.


# ── Tools ───────────────────────────────────────────────────────────────────


@mcp.tool(
    annotations={
        "title": "Track Korean DART filings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def track_korean_filings(
    company_corp_code: Optional[str] = None,
    days: int = 7,
    filing_type: Optional[str] = None,
    limit: int = 30,
    translate: bool = True,
    summarize: bool = False,
    license_key: Optional[str] = None,
    company_corp_codes: Optional[list[str]] = None,
    since: Optional[str] = None,
    material_only: bool = False,
    page: int = 1,
) -> list[Filing] | dict:
    """Track Korean DART (전자공시) stock filings in English — real-time corporate disclosures for KOSPI / KOSDAQ / KONEX / KRX listed companies: 5%-rule shareholding disclosures, M&A, periodic reports, capital issuance, insider trading, audit reports. Free tier.

    Use this tool when the user asks about: recent Korean stock filings, DART disclosures, Korean market data, KOSPI/KOSDAQ regulatory events, "track Korean DART filings", "what did Samsung / Hyundai / SK / LG / NAVER / Kakao / 셀트리온 file", company-specific filing history, periodic / major-event / issuance / shareholding / audit filings on Korean equities.

    **Free tier — no license required.** Returns raw DART filings exactly
    as the regulator surfaces them (filer name in Korean, filing type code,
    receipt number, optional EN translation of the title).

    **Important for LLM clients — read this before retrying after a paid-
    tool license error.** This tool returns *raw* filings only. It does NOT
    classify the filer. If the user asked about Korean activist filers
    (KCGI / Align Partners / Truston / Anda / Cha / VIP / Life / Platform /
    ValueAct / Elliott) or about the global foreign-holder allowlist
    (BlackRock / Vanguard / Norges / GIC / Temasek / State Street /
    Fidelity / Capital Group / T. Rowe Price / Wellington / Goldman /
    JPMorgan / Morgan Stanley / Citadel / Millennium / Bridgewater +
    others), the matching work happens in `monitor_activist_investors`
    and `monitor_foreign_holders` — both require a license_key argument.
    A response from this free tool to a "are activists filing on X?" or
    "is BlackRock holding X?" question is *raw filing data*, not a
    classification answer — say so to the user and surface the paid tool's
    license-required notice instead of pretending you've answered.

    **Batch scan for agents (experimental).** To check MULTIPLE companies for
    material disclosures since your last checkpoint in ONE call — instead of N
    separate calls — pass `company_corp_codes` (a list, ≤10) plus a `since`
    timestamp. This is the portfolio-monitoring / scan-since-checkpoint
    workflow: give it your watchlist's corp codes and the ISO timestamp of
    your previous check, optionally with `material_only=True`, and it returns
    every filing across those companies newer than that timestamp, merged and
    sorted newest-first. DART has no batch endpoint, so this fans out one
    cache-backed call per corp code — the ≤10 cap keeps a single call from
    blowing past DART's daily quota.

    Args:
        company_corp_code: 8-digit DART corp code (single company). Use
            `lookup_corp_code` first to resolve a company name. Omit to query
            all companies. Ignored when `company_corp_codes` (plural) is
            provided non-empty — the plural list takes precedence.
        company_corp_codes: OPTIONAL list of up to 10 corp codes for batch
            mode. When provided non-empty, the tool queries each corp code
            concurrently (one cache-backed DART call each), merges the
            results, and sorts newest-first — use this to scan a whole
            watchlist in one call. More than 10 codes raises a validation
            error (DART has no batch endpoint; this is N calls, so the cap
            protects the daily quota). Takes precedence over
            `company_corp_code` (singular) when both are given.
        since: OPTIONAL ISO-8601 date or datetime (e.g. '2026-05-01' or
            '2026-05-01T09:00:00'). When provided it is the cutoff instead of
            `days` — only filings with `filed_at >= since` are returned. Use
            it to fetch only what is new since your last checkpoint.
            `filed_at` is date-granular (KST), so the comparison is by calendar
            day: every filing on or after the `since` date is returned, even
            when `since` carries a time of day. A malformed value raises a
            validation error.
            When omitted, the `days` window is used exactly as before.
        material_only: OPTIONAL. When True, return only filings whose
            `red_flags` list is non-empty (governance/distress-tagged — see
            the red_flags catalog below). Applies to both single and batch
            queries. Reuses the existing red-flag tagging; adds no new
            classification.
        days: how many days back from today (KST), 1-30; the window is
            [today - days, today]. Ignored when `since` is provided.
        filing_type: optional one-letter code:
            A=periodic, B=major event, C=issuance, D=shareholding,
            E=other, F=audit, G=fund, H=ABS, I=exchange, J=FTC.
        limit: max filings per page (1-100, default 30). DART returns
            most-recent first; use `page` to reach older items.
            In batch mode (`company_corp_codes`) `limit` applies PER COMPANY,
            not to the merged set, so a heavy filer can never crowd a quieter
            company out of the results: an empty result for a company means
            that company genuinely filed nothing in the window. A batch call
            can therefore return up to `limit × len(company_corp_codes)` rows.
        translate: True to fill `title_en` via server-side LLM (cached).
        summarize: True to fill `summary_en` (≤200 words). Costs more — use
            sparingly. Long-form analysis should be done by the client LLM.
        license_key: subscription key. Required when KOREANPULSE_REQUIRE_LICENSE=1.
        page: 1-based page of `limit` results (default 1). When `next_page` is
            returned, call again with that value for older filings.

    Examples:
        - "What did Samsung Electronics file this week?" -> `lookup_corp_code("삼성전자")`,
          then `track_korean_filings(company_corp_code="00126380", days=7)`.
        - "Any distress signals across my watchlist since Monday?" ->
          `track_korean_filings(company_corp_codes=[...], since="2026-10-19", material_only=True)`.

    Errors: a `company_corp_code` that is not exactly 8 digits (a 6-digit KRX
    ticker, a company name) is rejected with a message naming the tool that
    converts it. Dates are KST; DART publishes on Korean business days only.

    Returns:
        A plain list of filings when the result is complete. Whenever there is
        something to tell you — nothing found, more pages exist, a company
        failed, translation unavailable — a dict instead:
        `{"filings": [...], "notes": ["..."], "window_kst": {"from", "to"},
        "next_page"?, "total_matches"?, "errors"?}`. Read `notes`: an empty
        `filings` with no `errors` means DART returned nothing for that
        window; `errors` means those companies are MISSING, not quiet.

        Filings are ordered by most recent first. Each filing carries:
        - `market`: listing venue from DART corp_cls — "KOSPI", "KOSDAQ",
          "KONEX", or "OTHER" (None when DART omits it). Use this instead of
          guessing KOSPI vs KOSDAQ from the company name.
        - `red_flags`: governance/distress tags inferred from the title:
          - cb_issuance — convertible bond issuance (전환사채권발행)
          - controlling_shareholder_change — largest-shareholder change (최대주주변경)
          - rehabilitation — court receivership / rehabilitation (회생절차)
          - audit_opinion — distress-only audit opinion (의견거절/한정/부적정);
            a clean ('적정') opinion is not tagged
          - disclosure_violation — unfaithful-disclosure designation (불성실공시)
          - rights_issue — paid-in capital increase (유상증자)
          - capital_reduction — capital reduction (감자)
          - management_designation — administrative-issue designation (관리종목)
          - delisting_risk — delisting event/risk (상장폐지)
          - trading_halt — trading suspension (거래정지)
          - reverse_split — share consolidation (주식병합)
          - short_term_borrowing — short-term borrowing disclosure (단기차입금)
          - going_concern — going-concern doubt (계속기업/존속능력)
        - `is_correction` / `previous_receipt_no`: whether this is a DART correction re-filing ([기재정정]/[첨부정정]), and the receipt_no of the original it amends when that original is in the same fetched window (None otherwise).
        - `query_total_count` / `data_fetched_at`: DART's full match count before this response's `limit` truncation, and the UTC as-of timestamp of the live fetch (None on rows served from cache).
    """
    logger.info("tool_call: track_korean_filings days=%d limit=%d translate=%s summarize=%s", days, limit, translate, summarize)
    await _gate(license_key, units=1 + (1 if summarize else 0))

    # Batch precedence: a non-empty plural list wins over the singular arg.
    batch_codes = [c.strip() for c in (company_corp_codes or []) if c and c.strip()]
    if len(batch_codes) > 10:
        raise ValueError(
            "track_korean_filings: `company_corp_codes` accepts at most 10 "
            f"corp codes per call (got {len(batch_codes)}). DART has no batch "
            "endpoint — each code is a separate quota-backed call, so the cap "
            "protects the daily quota. Split your watchlist into batches of 10."
        )
    batch_codes = [
        _check_corp_code(c, tool="track_korean_filings", arg="company_corp_codes") for c in batch_codes
    ]
    if batch_codes or not (company_corp_code and company_corp_code.strip()):
        company_corp_code = None  # plural list wins; blank string means "all companies"
    else:
        company_corp_code = _check_corp_code(
            company_corp_code, tool="track_korean_filings", arg="company_corp_code"
        )
    filing_type = _check_filing_type(filing_type, tool="track_korean_filings")
    limit = _clamp(limit, 1, 100)
    page = _clamp(page, 1, 1000)

    since_dt = _parse_since(since) if since else None

    days = _clamp(days, 1, 30)
    end_de = _kst_today()
    if since_dt is not None:
        # Narrow the DART window to the cutoff so we don't over-fetch.
        bgn_de = min(since_dt.date(), end_de)
    else:
        bgn_de = end_de - timedelta(days=days)
    window = _window(bgn_de, end_de)

    # One structured, greppable line marking the new agent batch-scan usage
    # pattern (multi-company or since-checkpoint), kept distinct from the
    # legacy single-company/days call above. No PII; license key presence
    # only, never its value.
    if len(batch_codes) > 1 or since_dt is not None:
        logger.info(
            "agent_batch_scan corp_code_count=%d cutoff=%s material_only=%s license_key_present=%s",
            len(batch_codes) if batch_codes else (1 if company_corp_code else 0),
            "since" if since_dt is not None else "days",
            material_only,
            license_key is not None,
        )

    def _wanted(f: Filing) -> bool:
        # `filed_at` is date-granular (KST midnight), so compare dates: a
        # `since` with a time of day must not drop filings made later that
        # same day (they also sit at midnight and would otherwise vanish).
        if since_dt is not None and f.filed_at.date() < since_dt.date():
            return False
        if material_only and not f.red_flags:
            return False
        return True

    # With a client-side filter the DART page must not be sized by `limit`
    # (see _scan_filings); without one a single `limit`-sized page suffices.
    predicate = _wanted if (material_only or since_dt is not None) else None
    notes: list[str] = []
    empty_hint = (
        "Widen `days` (max 30) or `since`, drop `filing_type`/`material_only`, or check the "
        "company with `lookup_corp_code`. DART publishes on KST business days."
    )

    if batch_codes:
        results = await asyncio.gather(
            *[
                _scan_filings(
                    corp_code=code, bgn_de=bgn_de, end_de=end_de, pblntf_ty=filing_type,
                    limit=limit, page=page, predicate=predicate,
                )
                for code in batch_codes
            ],
            return_exceptions=True,
        )
        failures = [(c, r) for c, r in zip(batch_codes, results) if isinstance(r, BaseException)]
        if len(failures) == len(batch_codes):
            raise failures[0][1]
        filings = []
        for code, res in zip(batch_codes, results):
            if isinstance(res, BaseException):
                continue
            # `limit` is PER COMPANY, applied before the merge: truncating the
            # merged set would let a heavy filer crowd a quieter one out, and
            # the caller could not tell "filed nothing" from "truncated away".
            filings.extend(res.rows)
            if res.more:
                notes.append(
                    f"{code}: more filings exist beyond the {limit} returned; pass page={page + 1}."
                )
            if not res.exhausted and res.total is not None and res.examined < res.total and predicate:
                notes.append(
                    f"{code}: INCOMPLETE SCAN ({res.examined} of {res.total} filings inspected)."
                )
        filings.sort(key=lambda f: f.filed_at, reverse=True)
        errors = [
            {"corp_code": c, "error": f"{type(r).__name__}: {r}"} for c, r in failures
        ]
        if errors:
            notes.insert(
                0,
                f"INCOMPLETE: {len(errors)} of {len(batch_codes)} companies failed and are missing from "
                "`filings` (see `errors`). Do not read their absence as 'filed nothing'. "
                "The other companies are cached, so retrying is cheap.",
            )
        elif not filings:
            notes.append(
                f"None of {', '.join(batch_codes)} filed anything matching in "
                f"{bgn_de}..{end_de} (KST). {empty_hint}"
            )
    else:
        scan = await _scan_filings(
            corp_code=company_corp_code, bgn_de=bgn_de, end_de=end_de, pblntf_ty=filing_type,
            limit=limit, page=page, predicate=predicate,
        )
        filings = scan.rows
        # Sort only when the since/material pipeline is engaged — the legacy
        # single-company/days path returns DART's native ordering untouched.
        if predicate is not None:
            filings.sort(key=lambda f: f.filed_at, reverse=True)
        errors = []
        notes.extend(
            _scan_notes(scan, what="filings", bgn=bgn_de, end=end_de, page=page, hint=empty_hint)
        )

    if translate or summarize:
        if translate:
            await _translate_rows(filings, notes, tool="track_korean_filings")
        if summarize and filings:
            translator = _get_translator()
            if _translation_unavailable(translator):
                notes.append("summarize=true was requested but no LLM backend is configured; `summary_en` is empty.")
            else:
                for f in filings:
                    if not f.summary_en:
                        try:
                            f.summary_en = await translator.summarize_ko(
                                f.title,
                                attribution=f.attribution,
                                labels={"tool": "track_korean_filings"},
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("summarize failed for %s: %s", f.receipt_no, exc)

    extra: dict[str, Any] = {}
    if batch_codes and errors:
        extra["errors"] = errors
    if not batch_codes and scan.more:
        extra["next_page"] = page + 1
        if predicate is None:
            extra["total_matches"] = scan.total
    return _envelope(filings, notes, window=window, **extra)


@mcp.tool(
    annotations={
        "title": "Resolve Korean company name to DART corp_code",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def lookup_corp_code(
    query: str,
    listed_only: bool = False,
    limit: int = 10,
    license_key: Optional[str] = None,
) -> list[CorpEntry] | dict:
    """Company name → DART corp_code resolver. 117K+ entities indexed (KOSPI + KOSDAQ + KONEX + unlisted). Free tier.

    Use this tool when the user mentions a Korean company by name and you need the DART corp_code as a precondition for `track_korean_filings`, `monitor_activist_investors`, or `monitor_foreign_holders`. Also use to disambiguate same-name listed vs unlisted entities.

    The DART index is Korean-only. Search with the Korean name ("삼성전자", "현대차" will not match — use the registered name "현대자동차"). About 35 very well-known companies also resolve from their English name ("Samsung Electronics", "SK hynix", "Kakao", "Celltrion"); for any other English name, translate or look up the Korean registered name first. Matching ignores case, spaces, punctuation and "(주)".

    Args:
        query: Korean company name or a substring of it, e.g. "삼성전자", "셀트리온", "SK하이닉스".
        listed_only: if True, only return companies with a KRX stock code.
        limit: max matches to return (1-50, default 10). Exact name first, then prefix, then listed, then shorter name.
        license_key: subscription key. Required when license gate is enabled.

    Returns:
        A list of CorpEntry (`corp_code` is the 8-digit input for other tools; `stock_code` is None for unlisted companies). When nothing matches, a dict `{"matches": [], "notes": [...]}` explains why and what to try next.
    """
    logger.info("tool_call: lookup_corp_code query=%s listed_only=%s limit=%d", str(query)[:30], listed_only, limit)
    await _gate(license_key, units=1)
    q = (query or "").strip()
    if not q:
        raise ValueError("lookup_corp_code: `query` is required, e.g. '삼성전자'.")
    matches = await lookup_by_name(q, listed_only=listed_only, limit=_clamp(limit, 1, 50))
    if matches:
        return matches
    notes = [f"No DART company name contains {q!r}" + (" among listed companies" if listed_only else "") + "."]
    if q.isdigit():
        notes.append(
            "A number is not a company name: 6 digits is a KRX ticker (use `resolve_stock_code`); "
            "8 digits is already a corp_code."
        )
    elif q.isascii():
        notes.append(
            "The DART index is in Korean. English names resolve only for ~35 well-known companies; "
            "retry with the Korean registered name (e.g. 'Hyundai Motor' -> '현대자동차')."
        )
    else:
        notes.append("Try a shorter fragment, drop suffixes such as '홀딩스', or retry without `listed_only`.")
    return {"matches": [], "notes": notes}


@mcp.tool(
    annotations={
        "title": "Resolve KRX 6-digit ticker to DART corp entry",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def resolve_stock_code(
    stock_code: str,
    license_key: Optional[str] = None,
) -> Optional[CorpEntry] | dict:
    """KRX 6-digit ticker → DART corp entry resolver. Free tier.

    Use this tool when the user provides a 6-digit Korean stock code (e.g. 005930 for Samsung Electronics, 000660 for SK hynix, 035420 for NAVER, 035720 for Kakao, 005380 for Hyundai Motor) and you need the company name + corp_code for downstream filings or industry-news lookups.

    Returns the entry (`corp_code`, `corp_name`, `stock_code`), or `null` when the code is not a listed KRX common-stock ticker in DART's index (check for typos; delisted tickers and ETFs are not in it). Accepts "5930", "005930" and "005930.KS".

    When the code is unresolved but looks like a Korean preferred-stock ticker (6 digits, non-zero last digit, e.g. 005935 for 삼성전자우), the response carries an additive `related_common_stock` hint pointing at the common-stock entry — the corp registry only maps common stock, so no preferred-stock corp_code is fabricated.
    """
    logger.info("tool_call: resolve_stock_code stock_code=%s", str(stock_code)[:10])
    await _gate(license_key, units=1)
    result = await lookup_by_stock_code(stock_code)
    if result is not None:
        return result

    hint = await _related_common_stock_hint(stock_code)
    if hint is not None:
        return {"related_common_stock": hint}
    return None


async def _related_common_stock_hint(stock_code: str) -> Optional[dict]:
    """Best-effort hint for a 6-digit code shaped like a Korean
    preferred-stock ticker that DART's corp registry doesn't resolve
    directly (the registry only maps common stock).

    Korean preferred tickers conventionally share the common stock's first
    5 digits with a non-zero last digit (e.g. 005935 for 삼성전자우 vs
    005930 for 삼성전자 common). This tries the common-stock candidate
    (last digit zeroed) and only returns a hint when that lookup actually
    resolves — never invents a preferred-stock corp_code/name.
    """
    code = normalize_stock_code(stock_code)
    if not (code.isdigit() and len(code) == 6 and code[-1] != "0"):
        return None
    common = await lookup_by_stock_code(code[:-1] + "0")
    if common is None:
        return None
    return {
        "stock_code": common.stock_code,
        "corp_name": common.corp_name,
        "note": "preferred-stock ticker; corp registry only maps common stock",
    }


@mcp.tool(
    annotations={
        "title": "Search Korean industry news (16 sectors)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def search_korean_industry_news(
    industries: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
    limit: int = 20,
    translate: bool = True,
    license_key: Optional[str] = None,
) -> list[Article] | dict:
    """Korean industry news search across 16 sectors with on-demand English translation. Sources: 전자신문 (etnews) + 한국경제 (hankyung) + The Korea Herald (English-native) + 지디넷코리아 (zdnet). Free tier.

    Use this tool when the user asks about: Korean industry trends, sector-specific news on Korean equities (Korean semiconductors / K-battery / K-shipbuilding / K-biotech / K-defense / Korean auto / EV charging / Korean AI / steel / petrochem / construction / fintech / gaming / e-commerce / telco / energy), recent corporate developments not yet captured in DART filings, English summaries of Korean industry coverage. Industry tags listed below — pass them in `industries` to filter.

    Args:
        industries: filter to one or more industry tags. Available:
            semiconductor, shipbuilding, battery, biotech, defense, auto,
            ev_charging, ai, steel, petrochem, construction, fintech, gaming,
            ecommerce, telco, energy. An unrecognized tag is never silently
            dropped or errored — see Returns below.
        sources: filter to source keys (etnews, hankyung, koreaherald, zdnet).
            None = all. koreaherald is English-native — its titles are
            returned as-is (no ko->en translation round-trip needed).
        limit: max articles (≤50).
        translate: server-side translates `title_en` for Korean-language
            sources. Cached aggressively. No-op for koreaherald (already
            English).
        license_key: required when license gate is enabled.

    Returns:
        A bare list of Articles sorted by published_at desc — same shape
        as before — when every requested `industries` tag is recognized
        (or `industries` is omitted). If one or more requested tags is NOT
        a supported industry, the return value is instead a dict:
        `{"articles": [...], "unsupported_industries": [...], "supported_industries": [...]}`
        — articles for the recognized tags still come back (an
        unsupported tag is dropped from the filter, not treated as an
        error), and the extra fields tell the caller which of their tags
        didn't match so they can retry with a supported one.
    """
    logger.info("tool_call: search_korean_industry_news industries=%s sources=%s limit=%d translate=%s", industries, sources, limit, translate)
    await _gate(license_key, units=1)

    wanted_industries = [i.strip().lower() for i in industries if i and i.strip()] if industries else []
    unsupported_industries = [i for i in wanted_industries if i not in INDUSTRY_KEYWORDS]
    wanted_sources = [k.strip().lower() for k in sources if k and k.strip()] if sources else []
    unknown_sources = [k for k in wanted_sources if k not in NEWS_SOURCE_BY_KEY]
    notes: list[str] = []
    if wanted_sources and len(unknown_sources) == len(wanted_sources):
        # Every requested source is unknown: silently falling back to "all
        # sources" would answer a different question than the one asked.
        raise ValueError(
            f"search_korean_industry_news: unknown source(s) {unknown_sources}; "
            f"valid `sources` keys are {list(NEWS_SOURCE_BY_KEY)}."
        )
    if unknown_sources:
        notes.append(f"Ignored unknown source key(s) {unknown_sources}; valid keys are {list(NEWS_SOURCE_BY_KEY)}.")

    failures: list[str] = []
    articles = await fetch_industry_news(
        industries=wanted_industries or None,
        source_keys=[k for k in wanted_sources if k in NEWS_SOURCE_BY_KEY] or None,
        limit=_clamp(limit, 1, 50),
        failures=failures,
    )
    if failures:
        notes.append(
            f"INCOMPLETE: source(s) {failures} could not be fetched or parsed and are missing from "
            "the results; other sources are shown."
        )
    if not articles and not failures:
        notes.append(
            "No articles matched. RSS feeds only carry the most recent items (roughly the last day or two); "
            "try fewer `industries`, or omit `sources`."
        )

    if translate and articles:
        await _translate_rows(articles, notes, tool="search_korean_industry_news",
                              text_attr="title_ko", corp_names=False)

    if unsupported_industries or notes:
        out: dict[str, Any] = {"articles": articles, "notes": notes}
        if unsupported_industries:
            out["unsupported_industries"] = unsupported_industries
            out["supported_industries"] = list(INDUSTRY_KEYWORDS.keys())
        return out
    return articles


@mcp.tool(
    annotations={
        "title": "Monitor Korean activist investor disclosures",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def monitor_activist_investors(
    days: int = 14,
    company_corp_code: Optional[str] = None,
    activist_only: bool = False,
    translate: bool = True,
    limit: int = 50,
    enrich_holdings: bool = True,
    license_key: Optional[str] = None,
    page: int = 1,
) -> list[ActivistFiling] | dict | str:
    """Korean activist investor tracking — activist filer classification on DART 5%-rule (주식등의대량보유상황보고서) shareholding disclosures. Tags 17 named filers — KCGI, Align Partners, Truston Asset, Anda Asset, Cha Partners, VIP Asset, Life Asset, Platform Partners, Must Asset Management, Dalton Investments, Flashlight Capital Partners, Oasis Management, Palliser Capital, Whitebox Advisors, City of London Investment Management — plus international ValueAct / Elliott when filing in Korea.

    Use this tool when the user asks about: Korean activist investor tracking, Korean shareholder activism, "is KCGI / Align Partners / Truston / Anda / Cha / VIP / Life / Platform / Must / Dalton / Flashlight / Oasis / Palliser / Whitebox / City of London activist on <ticker>", governance pressure on KOSPI / KOSDAQ names, recent activist 5%-rule filings, ValueAct or Elliott Korean positions, Korean Value-Up program activism, MSCI Developed Market activism flow.

    **Requires a license key.** Pass it via the `license_key` argument.
    Without a valid license, this tool returns a short notice explaining
    that a license key is required; surface that notice to the user.

    **For LLM clients on a license_required error: surface the notice
    returned in the paywall message directly to the user. Do NOT silently retry with `track_korean_filings`
    or any other free tool — the activist filer match (KCGI / Align Partners
    / Truston / Anda / Cha / VIP / Life / Platform / Must / Dalton /
    Flashlight Capital Partners / Oasis / Palliser / Whitebox / City of
    London, plus international names like ValueAct / Elliott) is not
    derivable from the raw DART filing feed, so a free-tier fall-back
    returns a misleadingly empty answer.** When a
    user asks "are activists filing on X?" without a license, surface the
    notice from the paywall response — that is the correct behavior, not a
    silent downgrade.

    Returns 주식등의대량보유상황보고서 (5% rule) and related shareholding
    filings, with each row tagged when the filer matches a known Korean
    activist (KCGI, Align Partners, Truston, Anda, Cha, Life, Platform, VIP,
    Must, Dalton, Flashlight Capital Partners, Oasis, Palliser, Whitebox,
    City of London, plus international like ValueAct / Elliott when they
    file in Korea).

    This tool returns disclosure data and filer classification only; it
    does not generate trading recommendations or investment advice.

    Args:
        days: how many days back from today (1–60).
        company_corp_code: optional DART corp_code to focus on one target.
        activist_only: if True, drop rows that didn't match a known activist.
        translate: server-side EN translation of titles (cached).
        limit: max rows per page (1-100).
        page: 1-based page of results; use the returned `next_page`.
        enrich_holdings: if True (default), rows matched to a known activist
            get their `holding_pct` / `holding_pct_change` / `holder_reporter_ko`
            filled from DART's majorstock.json (best-effort — a lookup
            failure leaves those fields None rather than failing the call).
            Capped at 8 distinct corp_codes per call.
        license_key: required when license gate is enabled.

    Scan behaviour: the allowlist is matched against the whole window, newest
    DART shareholding filings first, reading up to KOREANPULSE_MAX_SCAN_PAGES
    pages of 100 (default 10). If that cap is reached before the window is
    exhausted, the result says `INCOMPLETE SCAN` in `notes` — an empty answer
    is then NOT proof that no activist filed; narrow `days` or pass
    `company_corp_code`.

    Returns:
        ActivistFiling rows ordered by filing date desc — a plain list when
        complete, or `{"filings": [...], "notes": [...], "window_kst": {...},
        "next_page"?}` when there is something to report (empty result,
        another page, incomplete scan, translation unavailable). `query_total_count`
        / `data_fetched_at` carry DART's full match count before this
        response's `limit` truncation and the UTC as-of timestamp of the
        live fetch (None on rows served from cache).
    """
    logger.info("tool_call: monitor_activist_investors days=%d activist_only=%s limit=%d corp_code=%s license_key_set=%s", days, activist_only, limit, company_corp_code, license_key is not None)
    paywall = await _paid_gate(
        license_key,
        units=1 + (1 if activist_only else 0),
        tool_name="monitor_activist_investors",
    )
    if paywall:
        return paywall

    if company_corp_code and company_corp_code.strip():
        company_corp_code = _check_corp_code(
            company_corp_code, tool="monitor_activist_investors", arg="company_corp_code"
        )
    else:
        company_corp_code = None
    days = _clamp(days, 1, 60)
    limit = _clamp(limit, 1, 100)
    page = _clamp(page, 1, 1000)
    end_de = _kst_today()
    bgn_de = end_de - timedelta(days=days)

    # activist_only needs the allowlist applied across the whole window, not
    # just to the newest `limit` DART rows (see _scan_filings).
    scan = await _scan_filings(
        corp_code=company_corp_code, bgn_de=bgn_de, end_de=end_de, pblntf_ty="D",
        limit=limit, page=page,
        predicate=(lambda f: match_activist(f.filer_name_ko) is not None) if activist_only else None,
    )

    enriched: list[ActivistFiling] = []
    for f in scan.rows:
        label = match_activist(f.filer_name_ko)
        enriched.append(
            ActivistFiling(
                **f.model_dump(),
                is_likely_activist=label is not None,
                activist_label=label,
            )
        )

    notes = _scan_notes(
        scan, what="activist 5%-rule filings" if activist_only else "shareholding filings",
        bgn=bgn_de, end=end_de, page=page,
        hint=(
            "That means no allowlisted activist filed in the window, not that nobody did. "
            "Widen `days` (max 60) or pass `company_corp_code`."
        ) if activist_only else "Widen `days` (max 60) or pass `company_corp_code`.",
    )
    if not activist_only and enriched and not any(a.is_likely_activist for a in enriched):
        notes.append(
            "None of the returned filings matched the activist allowlist; use `activist_only=true` "
            "to search the whole window for allowlisted filers."
        )

    if enrich_holdings:
        matched = [a for a in enriched if a.is_likely_activist]
        if matched:
            await fill_holding_pct(matched, op="monitor_activist_investors")

    if translate and enriched:
        await _translate_rows(enriched, notes, tool="monitor_activist_investors")

    extra: dict[str, Any] = {"next_page": page + 1} if scan.more else {}
    return _envelope(enriched, notes, window=_window(bgn_de, end_de), **extra)


@mcp.tool(
    annotations={
        "title": "Monitor foreign 5%-rule holders on KOSPI/KOSDAQ",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def monitor_foreign_holders(
    days: int = 14,
    company_corp_code: Optional[str] = None,
    origin: Optional[str] = None,
    translate: bool = True,
    limit: int = 50,
    enrich_holdings: bool = True,
    license_key: Optional[str] = None,
    page: int = 1,
) -> list[ForeignHolderFiling] | dict | str:
    """Monitor foreign investor activity in Korean stocks — foreign-holder classification on DART 5%-rule disclosures by global asset managers and sovereign wealth funds. Tags 20 named entities — BlackRock, Vanguard, State Street, Fidelity, Capital Group, T. Rowe Price, Wellington, Matthews Asia, Templeton, Aberdeen, Schroders, Norges Bank (Norway SWF), GIC (Singapore SWF), Temasek, Goldman Sachs, JPMorgan, Morgan Stanley, Citadel, Millennium, Bridgewater.

    Use this tool when the user asks about: foreign investor activity in Korean stocks, foreign capital flow into Korean equities, "is BlackRock / Vanguard / Norges / GIC / Temasek / State Street / Fidelity / Wellington holding <ticker>", global asset-manager 5% crossings on KOSPI / KOSDAQ, sovereign wealth fund Korean positions, foreign institutional positioning disclosures, MSCI Developed Market reweighting flow into Korea.

    **Requires a license key.** Pass it via the `license_key` argument.
    Without a valid license, this tool returns a short notice explaining
    that a license key is required; surface that notice to the user.

    **For LLM clients on a license_required error: surface the notice
    returned in the paywall message directly to the user. Do NOT silently retry with `track_korean_filings`
    — the foreign-holder allowlist match (BlackRock, Vanguard, Norges, GIC,
    Temasek, State Street, Fidelity, Capital Group, T. Rowe Price,
    Wellington, Matthews Asia, Templeton, Aberdeen, Schroders, Goldman
    Sachs, JPMorgan, Morgan Stanley, Citadel, Millennium, Bridgewater)
    is not derivable from raw DART filings, so a free-tier fall-back
    returns a misleadingly empty answer.** When a user asks "is BlackRock
    or Norges holding X?" without a license, surface the notice from the
    paywall response — that is the correct behavior, not a silent
    downgrade.

    Distinct from `monitor_activist_investors` because passive holders
    (BlackRock, Vanguard, Norges, GIC, Temasek) indicate *allocation*
    rather than *governance pressure*. Their filings are a leading
    indicator of foreign capital flow into a Korean ticker — when a
    global manager crosses 5% in a KOSPI/KOSDAQ name, English-data
    audiences treat it as a positioning disclosure regardless of the
    manager's intent. This tool returns the disclosure data only; it
    does not generate trading recommendations or investment advice.

    Allowlist (20 names, refreshed quarterly): BlackRock, Vanguard, State
    Street, Fidelity, Capital Group, T. Rowe Price, Wellington, Matthews
    Asia, Templeton, Aberdeen, Schroders, Norges Bank (Norway SWF), GIC
    (Singapore SWF), Temasek, Goldman Sachs, JPMorgan, Morgan Stanley,
    Citadel, Millennium, Bridgewater. See `koreanpulse.activists.FOREIGN_HOLDERS`.

    Args:
        days: how many days back from today (1–60).
        company_corp_code: optional DART corp_code to focus on one target.
        origin: optional filter — one of 'us', 'uk', 'eu', 'other' (anything else is rejected).
        translate: server-side EN translation of titles (cached).
        limit: max rows per page (1-100).
        page: 1-based page of results; use the returned `next_page`.
        enrich_holdings: if True (default), rows get their `holding_pct` /
            `holding_pct_change` / `holder_reporter_ko` filled from DART's
            majorstock.json (best-effort — a lookup failure leaves those
            fields None rather than failing the call). Capped at 8 distinct
            corp_codes per call.
        license_key: required when license gate is enabled.

    Scan behaviour: the allowlist is matched against the whole window, newest
    DART shareholding filings first, reading up to KOREANPULSE_MAX_SCAN_PAGES
    pages of 100 (default 10). If the cap is reached first, `notes` says
    `INCOMPLETE SCAN` and an empty answer is not proof of absence.

    Returns:
        ForeignHolderFiling rows ordered by filing date desc — a plain list
        when complete, or `{"filings": [...], "notes": [...], "window_kst":
        {...}, "next_page"?}` when there is something to report. Each row
        carries `holder_label` (canonical English) and `holder_origin`.
        `query_total_count` / `data_fetched_at` carry DART's full match
        count before this response's `limit` truncation and the UTC as-of
        timestamp of the live fetch (None on rows served from cache).
    """
    logger.info("tool_call: monitor_foreign_holders days=%d limit=%d corp_code=%s license_key_set=%s", days, limit, company_corp_code, license_key is not None)
    paywall = await _paid_gate(
        license_key,
        units=1,
        tool_name="monitor_foreign_holders",
    )
    if paywall:
        return paywall

    if company_corp_code and company_corp_code.strip():
        company_corp_code = _check_corp_code(
            company_corp_code, tool="monitor_foreign_holders", arg="company_corp_code"
        )
    else:
        company_corp_code = None
    origin_filter = origin.lower().strip() if origin and origin.strip() else None
    valid_origins = sorted({r.origin for r in FOREIGN_HOLDERS})
    if origin_filter and origin_filter not in valid_origins:
        raise ValueError(
            f"monitor_foreign_holders: `origin` must be one of {valid_origins} (or omitted); "
            f"got {origin!r}."
        )
    days = _clamp(days, 1, 60)
    limit = _clamp(limit, 1, 100)
    page = _clamp(page, 1, 1000)
    end_de = _kst_today()
    bgn_de = end_de - timedelta(days=days)

    def _is_wanted(f: Filing) -> bool:
        m = match_foreign_holder(f.filer_name_ko)
        return m is not None and (origin_filter is None or m.origin == origin_filter)

    # Every returned row must be an allowlist match, so the match runs inside
    # the page scan: sizing the DART page by `limit` and filtering afterwards
    # examined only the newest `limit` shareholding filings of ALL companies.
    scan = await _scan_filings(
        corp_code=company_corp_code, bgn_de=bgn_de, end_de=end_de, pblntf_ty="D",
        limit=limit, page=page, predicate=_is_wanted,
    )

    enriched: list[ForeignHolderFiling] = []
    for f in scan.rows:
        match = match_foreign_holder(f.filer_name_ko)
        if match is None:  # unreachable: predicate already matched
            continue
        enriched.append(
            ForeignHolderFiling(
                **f.model_dump(),
                holder_label=match.canonical,
                holder_origin=match.origin,
            )
        )

    notes = _scan_notes(
        scan, what="allowlisted foreign-holder 5%-rule filings", bgn=bgn_de, end=end_de, page=page,
        hint=(
            "That means no allowlisted holder filed in the window"
            + (f" with origin={origin_filter!r}" if origin_filter else "")
            + ", not that nobody did. Widen `days` (max 60) or pass `company_corp_code`."
        ),
    )

    if enrich_holdings and enriched:
        await fill_holding_pct(enriched, op="monitor_foreign_holders")

    if translate and enriched:
        await _translate_rows(enriched, notes, tool="monitor_foreign_holders")

    extra: dict[str, Any] = {"next_page": page + 1} if scan.more else {}
    return _envelope(enriched, notes, window=_window(bgn_de, end_de), **extra)


@mcp.tool(
    annotations={
        "title": "koreanpulse server self-description",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def koreanpulse_about() -> dict:
    """Server self-description — capability matrix, tool catalog, named-entity tag counts, supported query patterns, primary sources. Free tier.

    Use this tool when an agent first connects and needs the capability matrix to decide whether this server can answer the user's question, or when the user asks "what can koreanpulse do" or "what data sources does this MCP server provide". Returns a structured dict that downstream agents can ingest directly.
    """
    logger.info("tool_call: koreanpulse_about")
    n_corp = 0
    try:
        n_corp = await ensure_index_loaded()
    except Exception:  # noqa: BLE001
        n_corp = -1  # not loaded yet (no API key in env)
    return {
        "name": "koreanpulse",
        "version": __version__,
        "description": (
            "Korean stock market intelligence MCP for AI assistants and agents. "
            "Connects ChatGPT / Claude / Cursor / FastMCP agents to Korean (KRX / "
            "KOSPI / KOSDAQ) equity data: real-time DART corporate disclosures, "
            "foreign investor holding changes, activist investor campaigns, and "
            "classified Korean industry news — all in English. "
            "named-entity tagging via a maintained allowlist (17 Korean activist + "
            "20 global passive investor names) that the raw DART feed does not derive. "
            "Data and intelligence only — not buy/sell recommendations."
        ),
        "capability_tags": [
            "korean-equity",
            "kospi",
            "kosdaq",
            "konex",
            "krx",
            "dart-filings",
            "5-percent-rule",
            "shareholding-disclosure",
            "activist-investor",
            "foreign-holder",
            "sovereign-wealth-fund",
            "korean-industry-news",
            "english-translation",
            "msci-developed-market",
            "korea-value-up",
        ],
        "supported_query_patterns": [
            "5%-rule filings on <ticker or company>",
            "DART filings on <ticker or company> in last <N> days",
            "is <activist filer> filing on <ticker>",
            "is <foreign holder> holding <ticker>",
            "Korean <industry> news in last <N> days",
            "resolve KRX 6-digit ticker <code> to company",
            "find DART corp_code for <Korean company name>",
            "what did <Korean company> file recently",
            "foreign 5%-rule disclosures on KOSPI/KOSDAQ",
            "Korean activist disclosures (KCGI, Align, Truston, Anda)",
        ],
        "primary_sources": [
            "DART (Korea Financial Supervisory Service / 전자공시)",
            "전자신문 (etnews) RSS",
            "한국경제 (hankyung) RSS",
            "The Korea Herald RSS (English-native)",
            "지디넷코리아 (zdnet) RSS",
        ],
        "tools_free": [
            "track_korean_filings",
            "lookup_corp_code",
            "resolve_stock_code",
            "search_korean_industry_news",
            "koreanpulse_about",
        ],
        "tools_paid": [
            "monitor_activist_investors",
            "monitor_foreign_holders",
        ],
        "tools_planned": [
            "digest_analyst_reports",
            "get_ma_pipeline",
            "track_government_policy",
            "summarize_korean_earnings_call",
        ],
        "classifier_counts": {
            "korean_activists": len(KOREAN_ACTIVISTS),
            "foreign_holders": len(FOREIGN_HOLDERS),
            "industry_tags": len(INDUSTRY_KEYWORDS),
        },
        "example_queries": [
            "What 5%-rule filings hit Samsung Electronics this week?",
            "Are KCGI or Align Partners filing on any KOSPI names today?",
            "Show me last 7 days of foreign-holder 5%-rule filings (BlackRock, Vanguard, Norges, GIC).",
            "Any Korean semiconductor industry news in the last 24 hours?",
            "Find the DART corp_code for SK hynix.",
            "What did Hyundai Motor file in DART recently?",
        ],
        "license_gated_tools": {
            "tools": ["monitor_activist_investors", "monitor_foreign_holders"],
            "argument": "license_key",
            "self_host": "https://github.com/whdrnr2583-cmd/koreanpulse",
            "more_info": "https://koreanpulse.dev/#pricing",
            "note": (
                "The activist filer matching and foreign-holder allowlist run "
                "server-side and require a license key. They are not available via "
                "OSS self-host (github.com/whdrnr2583-cmd/koreanpulse), which is free "
                "but uses your own DART API key without the named-entity allowlist tagging."
            ),
        },
        "corp_index_size": n_corp,
        "homepage": "https://koreanpulse.dev",
        "endpoint": "https://mcp.koreanpulse.dev/mcp",
        "transport": "streamable-http",
        "endpoint_status": (
            "paused since 2026-09-21; the hosted endpoint does not respond. "
            "Run the self-hosted install instead (pip install koreanpulse, stdio)."
        ),
    }


def _startup_warnings() -> list[str]:
    """Configuration problems worth showing at launch, before the first tool
    call fails. Written to stderr via logging (stdout carries MCP traffic).
    Never includes secret values."""
    out: list[str] = []
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        out.append(
            "DART_API_KEY is not set: every DART tool will fail until it is. "
            "Get a free key at https://opendart.fss.or.kr/ and add it to the MCP client's "
            "`env` block (or a .env file)."
        )
    elif key.lower().startswith("your-"):
        out.append("DART_API_KEY looks like the .env.example placeholder, not a real key.")
    translator_ready = True
    try:
        translator_ready = _get_translator().configured
    except Exception as exc:  # noqa: BLE001 - e.g. an invalid CACHE_MODE value
        out.append(f"Translation is misconfigured: {exc}")
        translator_ready = True
    if not translator_ready:
        out.append(
            "No translation key (OPENAI_API_KEY / ANTHROPIC_API_KEY): tools still work, "
            "but `title_en` / `corp_name_en` stay empty (Korean text is returned)."
        )
    return out


def main() -> None:
    """Console-script entry point — runs the MCP server on stdio."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )
    logger.info("koreanpulse %s starting; state directory %s", __version__, data_dir())
    for line in _startup_warnings():
        logger.warning("%s", line)

    # Production safety: refuse to start if the operator asked for license
    # enforcement without the webhook-worker validate path. Otherwise the
    # in-memory store would be local to this MCP process and never see keys
    # issued by the webhook process.
    if _require_license():
        if os.environ.get("DATABASE_URL", "").strip():
            raise RuntimeError(POSTGRES_REMOVED_MESSAGE)
        if not (
            os.environ.get("KOREANPULSE_VALIDATE_URL", "").strip()
            and os.environ.get("KOREANPULSE_CACHE_SHARED_SECRET", "").strip()
        ):
            raise RuntimeError(
                "KOREANPULSE_REQUIRE_LICENSE=1 but the webhook validate path "
                "is not wired. Set KOREANPULSE_VALIDATE_URL and "
                "KOREANPULSE_CACHE_SHARED_SECRET."
            )

    mcp.run()


if __name__ == "__main__":
    main()
