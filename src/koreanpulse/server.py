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
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from agentprod import CostTracker
from fastmcp import FastMCP

from koreanpulse import __version__
from koreanpulse._enrich import fill_corp_name_en, fill_holding_pct
from koreanpulse.activists import (
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
    LicenseError,
    validate_license_or_raise,
)
from koreanpulse.models import ActivistFiling, Article, Filing, ForeignHolderFiling
from koreanpulse.news import INDUSTRY_KEYWORDS, fetch_industry_news
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
_cache = FileCache(root=".data/cache")
_cost_tracker = CostTracker(jsonl_path=".data/cost.jsonl")
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


async def _fill_title_en(filings: list, translator: Translator, *, tool: str) -> None:
    """Fill `title_en` on filings concurrently, deduping identical titles.

    Identical titles (common: many filings share the same DART report name)
    are translated exactly once per call, so the cache never sees duplicate
    in-flight misses. A failed translation logs a warning and leaves that
    filing's `title_en` unset — the filing itself is always kept, with the
    Korean `title` still present (same fallback as the old sequential loop).
    """
    pending: dict[str, list] = {}
    for f in filings:
        if not f.title_en and f.title:
            pending.setdefault(f.title, []).append(f)
    if not pending:
        return

    sem = asyncio.Semaphore(_TRANSLATE_CONCURRENCY)

    async def _one(title: str) -> None:
        async with sem:
            try:
                out = await translator.translate_ko_to_en(title, labels={"tool": tool})
            except Exception as exc:  # noqa: BLE001
                group = pending[title]
                logger.warning(
                    "translate failed for %s (%d filing(s)): %s",
                    group[0].receipt_no, len(group), exc,
                )
                return
        for f in pending[title]:
            f.title_en = out

    await asyncio.gather(*(_one(t) for t in pending))


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
            f"classifiers run server-side on the hosted koreanpulse service. "
            f"OSS self-host (github.com/whdrnr2583-cmd/koreanpulse + your own "
            f"DART API key) is free but does NOT include these classifiers, so "
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
) -> list[Filing]:
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
            `filed_at` is date-granular (KST), so a time component filters at
            day boundaries. A malformed value raises a validation error.
            When omitted, the `days` window is used exactly as before.
        material_only: OPTIONAL. When True, return only filings whose
            `red_flags` list is non-empty (governance/distress-tagged — see
            the red_flags catalog below). Applies to both single and batch
            queries. Reuses the existing red-flag tagging; adds no new
            classification.
        days: how many days back from today (1–30). Ignored when `since` is
            provided.
        filing_type: optional one-letter code:
            A=periodic, B=major event, C=issuance, D=shareholding,
            E=other, F=audit, G=fund, H=ABS, I=exchange, J=FTC.
        limit: max filings to return (≤100). DART returns most-recent first,
            so on a busy window the older end of the range is dropped first.
            Narrow `days` or `filing_type` if you need older items.
            In batch mode (`company_corp_codes`) `limit` applies PER COMPANY,
            not to the merged set, so a heavy filer can never crowd a quieter
            company out of the results: an empty result for a company means
            that company genuinely filed nothing in the window. A batch call
            can therefore return up to `limit × len(company_corp_codes)` rows.
        translate: True to fill `title_en` via server-side LLM (cached).
        summarize: True to fill `summary_en` (≤200 words). Costs more — use
            sparingly. Long-form analysis should be done by the client LLM.
        license_key: subscription key. Required when KOREANPULSE_REQUIRE_LICENSE=1.

    Returns:
        Filings ordered by most recent first. Each filing carries:
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

    since_dt = _parse_since(since) if since else None

    days = max(1, min(days, 30))
    end_de = _kst_today()
    if since_dt is not None:
        # Narrow the DART window to the cutoff so we don't over-fetch.
        bgn_de = min(since_dt.date(), end_de)
    else:
        bgn_de = end_de - timedelta(days=days)

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

    def _apply_filters(rows: list[Filing]) -> list[Filing]:
        if since_dt is not None:
            rows = [f for f in rows if f.filed_at >= since_dt]
        if material_only:
            rows = [f for f in rows if f.red_flags]
        return rows

    if batch_codes:
        per_corp = await asyncio.gather(
            *[
                list_filings_cached(
                    cache=_cache,
                    corp_code=code,
                    bgn_de=bgn_de,
                    end_de=end_de,
                    pblntf_ty=filing_type,
                    page_count=min(limit, 100),
                )
                for code in batch_codes
            ]
        )
        # `limit` is PER COMPANY in batch mode, applied before the merge.
        # Truncating the merged set instead would let a heavy filer crowd a
        # quieter one out entirely, and the caller could not tell "this company
        # filed nothing" from "this company was truncated away" — a false
        # all-clear, which is the worst failure mode for a portfolio monitor.
        # Cost: batch mode can return up to limit × len(batch_codes) rows.
        filings = [f for rows in per_corp for f in _apply_filters(rows)[:limit]]
        filings.sort(key=lambda f: f.filed_at, reverse=True)
    else:
        filings = await list_filings_cached(
            cache=_cache,
            corp_code=company_corp_code,
            bgn_de=bgn_de,
            end_de=end_de,
            pblntf_ty=filing_type,
            page_count=min(limit, 100),
        )
        filings = _apply_filters(filings)
        # Sort only when the since/material pipeline is engaged — the legacy
        # single-company/days path returns DART's native ordering untouched
        # (zero behavior change when the new args are omitted).
        if since_dt is not None or material_only:
            filings.sort(key=lambda f: f.filed_at, reverse=True)
        filings = filings[:limit]

    if translate or summarize:
        translator = _get_translator()
        if translate:
            await _fill_title_en(filings, translator, tool="track_korean_filings")
        for f in filings:
            if summarize and not f.summary_en:
                try:
                    f.summary_en = await translator.summarize_ko(
                        f.title,
                        attribution=f.attribution,
                        labels={"tool": "track_korean_filings"},
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("summarize failed for %s: %s", f.receipt_no, exc)
        if translate:
            await fill_corp_name_en(filings, translator, op="track_korean_filings")

    return filings


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
) -> list[CorpEntry]:
    """Korean company name → DART corp_code resolver. 117K+ entities indexed (KOSPI + KOSDAQ + KONEX + unlisted). Free tier.

    Use this tool when the user mentions a Korean company by name (Korean characters or English/romanized) and you need the DART corp_code as a precondition for `track_korean_filings`, `monitor_activist_investors`, or `monitor_foreign_holders`. Also use to disambiguate same-name listed vs unlisted entities.

    Args:
        query: substring of the Korean corp name. Examples: "삼성전자", "현대차", "셀트리온".
        listed_only: if True, only return companies with a KRX stock code.
        limit: max matches to return.
        license_key: subscription key. Required when license gate is enabled.

    Returns:
        List of CorpEntry. Use the `corp_code` field as input to other tools.
    """
    logger.info("tool_call: lookup_corp_code query=%s listed_only=%s limit=%d", str(query)[:30], listed_only, limit)
    await _gate(license_key, units=1)
    return await lookup_by_name(query, listed_only=listed_only, limit=limit)


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

    unsupported_industries = (
        [i for i in industries if i not in INDUSTRY_KEYWORDS] if industries else []
    )

    articles = await fetch_industry_news(
        industries=industries, source_keys=sources, limit=min(limit, 50)
    )

    if translate and articles:
        translator = _get_translator()
        for a in articles:
            if not a.title_en:
                try:
                    a.title_en = await translator.translate_ko_to_en(
                        a.title_ko, labels={"tool": "search_korean_industry_news"}
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("translate failed for article: %s", exc)

    if unsupported_industries:
        return {
            "articles": articles,
            "unsupported_industries": unsupported_industries,
            "supported_industries": list(INDUSTRY_KEYWORDS.keys()),
        }
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
) -> list[ActivistFiling] | str:
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
        limit: max rows (≤100).
        enrich_holdings: if True (default), rows matched to a known activist
            get their `holding_pct` / `holding_pct_change` / `holder_reporter_ko`
            filled from DART's majorstock.json (best-effort — a lookup
            failure leaves those fields None rather than failing the call).
            Capped at 8 distinct corp_codes per call.
        license_key: required when license gate is enabled.

    Returns:
        ActivistFiling rows ordered by filing date desc. `query_total_count`
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

    days = max(1, min(days, 60))
    end_de = _kst_today()
    bgn_de = end_de - timedelta(days=days)

    filings = await list_filings_cached(
        cache=_cache,
        corp_code=company_corp_code,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty="D",  # 지분공시 (shareholding disclosures)
        page_count=min(limit, 100),
    )

    enriched: list[ActivistFiling] = []
    for f in filings:
        label = match_activist(f.filer_name_ko)
        af = ActivistFiling(
            **f.model_dump(),
            is_likely_activist=label is not None,
            activist_label=label,
        )
        enriched.append(af)

    if activist_only:
        enriched = [a for a in enriched if a.is_likely_activist]

    enriched = enriched[:limit]

    if enrich_holdings:
        matched = [a for a in enriched if a.is_likely_activist]
        if matched:
            await fill_holding_pct(matched, op="monitor_activist_investors")

    if translate and enriched:
        translator = _get_translator()
        for af in enriched:
            if not af.title_en:
                try:
                    af.title_en = await translator.translate_ko_to_en(
                        af.title, labels={"tool": "monitor_activist_investors"}
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("translate failed for %s: %s", af.receipt_no, exc)
        await fill_corp_name_en(enriched, translator, op="monitor_activist_investors")

    return enriched


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
) -> list[ForeignHolderFiling] | str:
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
        origin: optional filter — one of 'us', 'uk', 'eu', 'other'.
        translate: server-side EN translation of titles (cached).
        limit: max rows (≤100).
        enrich_holdings: if True (default), rows get their `holding_pct` /
            `holding_pct_change` / `holder_reporter_ko` filled from DART's
            majorstock.json (best-effort — a lookup failure leaves those
            fields None rather than failing the call). Capped at 8 distinct
            corp_codes per call.
        license_key: required when license gate is enabled.

    Returns:
        ForeignHolderFiling rows ordered by filing date desc. Each row
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

    days = max(1, min(days, 60))
    end_de = _kst_today()
    bgn_de = end_de - timedelta(days=days)

    filings = await list_filings_cached(
        cache=_cache,
        corp_code=company_corp_code,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty="D",  # 지분공시 (shareholding disclosures)
        page_count=min(limit, 100),
    )

    enriched: list[ForeignHolderFiling] = []
    for f in filings:
        match = match_foreign_holder(f.filer_name_ko)
        if match is None:
            continue
        if origin and match.origin != origin.lower().strip():
            continue
        fhf = ForeignHolderFiling(
            **f.model_dump(),
            holder_label=match.canonical,
            holder_origin=match.origin,
        )
        enriched.append(fhf)

    enriched = enriched[:limit]

    if enrich_holdings and enriched:
        await fill_holding_pct(enriched, op="monitor_foreign_holders")

    if translate and enriched:
        translator = _get_translator()
        for fhf in enriched:
            if not fhf.title_en:
                try:
                    fhf.title_en = await translator.translate_ko_to_en(
                        fhf.title, labels={"tool": "monitor_foreign_holders"}
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("translate failed for %s: %s", fhf.receipt_no, exc)
        await fill_corp_name_en(enriched, translator, op="monitor_foreign_holders")

    return enriched


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
    """Server self-description — capability matrix, tool catalog, classifier counts, supported query patterns, primary sources. Free tier.

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
            "37 named-entity classifiers (17 Korean activists + 20 global passive "
            "holders) that the raw DART feed does not derive. "
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
            "korean_activists": 17,
            "foreign_holders": 20,
            "industry_tags": 16,
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
            "note": (
                "The activist filer matching and foreign-holder allowlist run "
                "server-side and require a license key. They are not available via "
                "OSS self-host (github.com/whdrnr2583-cmd/koreanpulse), which is free "
                "but uses your own DART API key without the named-entity classifiers."
            ),
        },
        "corp_index_size": n_corp,
        "homepage": "https://koreanpulse.dev",
        "endpoint": "https://mcp.koreanpulse.dev/mcp",
        "transport": "streamable-http",
    }


def main() -> None:
    """Console-script entry point — runs the MCP server on stdio."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )

    # Production safety: refuse to start if the operator asked for license
    # enforcement without wiring Postgres. Otherwise the in-memory store
    # would be local to this MCP process and never see keys issued by the
    # webhook process. Postgres autoconnect itself is lazy (first tool call).
    if _require_license() and not os.environ.get("DATABASE_URL", "").strip():
        raise RuntimeError(
            "KOREANPULSE_REQUIRE_LICENSE=1 but DATABASE_URL is not set. "
            "The MCP server and the webhook process must share a Postgres "
            "license store. See docs/POSTGRES.md."
        )

    mcp.run()


if __name__ == "__main__":
    main()
