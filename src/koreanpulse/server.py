"""koreanpulse MCP server entry point.

Wires the FastMCP server with all currently shipped tools. Run with:

    DART_API_KEY=...           # required
    ANTHROPIC_API_KEY=...      # required if you want server-side translation
    KOREANPULSE_REQUIRE_LICENSE=1   # optional, off by default in dev
    koreanpulse

Or import `mcp` and mount it inside another FastMCP app.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from agentprod import CostTracker
from fastmcp import FastMCP

from koreanpulse import __version__
from koreanpulse._enrich import fill_corp_name_en
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
)
from koreanpulse.dart import list_filings_cached, set_default_cache as _set_dart_cache
from koreanpulse.license import (
    LicenseError,
    validate_license_or_raise,
)
from koreanpulse.models import ActivistFiling, Article, Filing, ForeignHolderFiling
from koreanpulse.news import fetch_industry_news
from koreanpulse.translate import Translator

# DART filings are stamped in KST (UTC+9). When a US/EU user asks for
# "today" or "last 7 days" the window must follow DART's clock, not the
# caller's local one — otherwise we'd show empty/stale windows for half
# the planet.
_KST = timezone(timedelta(hours=9))


def _kst_today() -> date:
    return datetime.now(_KST).date()


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
    never forward the activation URL to the user. Returning a normal string
    forces the message through the success path so the LLM hands it to the
    user verbatim and the OSS install URL is actually clickable.
    """
    try:
        await validate_license_or_raise(license_key, cost_units=units)
        return None
    except LicenseError:
        return (
            f"`{tool_name}` requires a license key. Pass a `license_key` "
            f"argument when calling this tool. License keys are emailed to "
            f"subscribers on the hosted koreanpulse service — visit "
            f"koreanpulse.dev for details. OSS self-host "
            f"(github.com/whdrnr2583-cmd/koreanpulse + your own DART API key) "
            f"is free but does not include activist/foreign-holder classifiers."
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
    classification answer — say so to the user and surface the activation
    URL from the paywall response instead of pretending you've answered.

    Args:
        company_corp_code: 8-digit DART corp code. Use `lookup_corp_code` first
            to resolve a company name. Omit to query all companies.
        days: how many days back from today (1–30).
        filing_type: optional one-letter code:
            A=periodic, B=major event, C=issuance, D=shareholding,
            E=other, F=audit, G=fund, H=ABS, I=exchange, J=FTC.
        limit: max filings to return (≤100). DART returns most-recent first,
            so on a busy window the older end of the range is dropped first.
            Narrow `days` or `filing_type` if you need older items.
        translate: True to fill `title_en` via server-side LLM (cached).
        summarize: True to fill `summary_en` (≤200 words). Costs more — use
            sparingly. Long-form analysis should be done by the client LLM.
        license_key: subscription key. Required when KOREANPULSE_REQUIRE_LICENSE=1.

    Returns:
        Filings ordered by most recent first.
    """
    logger.info("tool_call: track_korean_filings days=%d limit=%d translate=%s summarize=%s", days, limit, translate, summarize)
    await _gate(license_key, units=1 + (1 if summarize else 0))

    days = max(1, min(days, 30))
    end_de = _kst_today()
    bgn_de = end_de - timedelta(days=days)

    filings = await list_filings_cached(
        cache=_cache,
        corp_code=company_corp_code,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty=filing_type,
        page_count=min(limit, 100),
    )
    filings = filings[:limit]

    if translate or summarize:
        translator = _get_translator()
        for f in filings:
            if translate and not f.title_en:
                try:
                    f.title_en = await translator.translate_ko_to_en(
                        f.title, labels={"tool": "track_korean_filings"}
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("translate failed for %s: %s", f.receipt_no, exc)
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
) -> Optional[CorpEntry]:
    """KRX 6-digit ticker → DART corp entry resolver. Free tier.

    Use this tool when the user provides a 6-digit Korean stock code (e.g. 005930 for Samsung Electronics, 000660 for SK hynix, 035420 for NAVER, 035720 for Kakao, 005380 for Hyundai Motor) and you need the company name + corp_code for downstream filings or industry-news lookups.
    """
    logger.info("tool_call: resolve_stock_code stock_code=%s", str(stock_code)[:10])
    await _gate(license_key, units=1)
    return await lookup_by_stock_code(stock_code)


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
) -> list[Article]:
    """Korean industry news search across 16 sectors with on-demand English translation. Sources: 전자신문 (etnews) + 한국경제 (hankyung). Free tier.

    Use this tool when the user asks about: Korean industry trends, sector-specific news on Korean equities (Korean semiconductors / K-battery / K-shipbuilding / K-biotech / K-defense / Korean auto / EV charging / Korean AI / steel / petrochem / construction / fintech / gaming / e-commerce / telco / energy), recent corporate developments not yet captured in DART filings, English summaries of Korean industry coverage. Industry tags listed below — pass them in `industries` to filter.

    Args:
        industries: filter to one or more industry tags. Available:
            semiconductor, shipbuilding, battery, biotech, defense, auto,
            ev_charging, ai, steel, petrochem, construction, fintech, gaming,
            ecommerce, telco, energy.
        sources: filter to source keys (etnews, hankyung). None = all.
        limit: max articles (≤50).
        translate: server-side translates `title_en`. Cached aggressively.
        license_key: required when license gate is enabled.

    Returns:
        Articles sorted by published_at desc.
    """
    logger.info("tool_call: search_korean_industry_news industries=%s sources=%s limit=%d translate=%s", industries, sources, limit, translate)
    await _gate(license_key, units=1)

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
    license_key: Optional[str] = None,
) -> list[ActivistFiling] | str:
    """Korean activist investor tracking — activist filer classification on DART 5%-rule (주식등의대량보유상황보고서) shareholding disclosures. Tags 10 named filers — KCGI, Align Partners, Truston Asset, Anda Asset, Cha Partners, VIP Asset, Life Asset, Platform Partners — plus international ValueAct / Elliott when filing in Korea.

    Use this tool when the user asks about: Korean activist investor tracking, Korean shareholder activism, "is KCGI / Align Partners / Truston / Anda / Cha / VIP / Life / Platform activist on <ticker>", governance pressure on KOSPI / KOSDAQ names, recent activist 5%-rule filings, ValueAct or Elliott Korean positions, Korean Value-Up program activism, MSCI Developed Market activism flow.

    **Requires a license key.** Pass it via the `license_key` argument.
    Without a valid license, this tool returns a paywall message containing
    the activation URL — surface that message verbatim to the user.

    **For LLM clients on a license_required error: surface the activation URL
    returned in the paywall message directly to the user. Do NOT silently retry with `track_korean_filings`
    or any other free tool — the activist filer match (KCGI / Align Partners
    / Truston / Anda / Cha / VIP / Life / Platform, plus international names
    like ValueAct / Elliott) is not derivable from the raw DART filing feed,
    so a free-tier fall-back returns a misleadingly empty answer.** When a
    user asks "are activists filing on X?" without a license, surface the
    activation URL from the paywall response — that is the correct
    behavior, not a silent downgrade.

    Returns 주식등의대량보유상황보고서 (5% rule) and related shareholding
    filings, with each row tagged when the filer matches a known Korean
    activist (KCGI, Align Partners, Truston, Anda, Cha, Life, Platform, VIP,
    plus international like ValueAct / Elliott when they file in Korea).

    Args:
        days: how many days back from today (1–60).
        company_corp_code: optional DART corp_code to focus on one target.
        activist_only: if True, drop rows that didn't match a known activist.
        translate: server-side EN translation of titles (cached).
        limit: max rows (≤100).
        license_key: required when license gate is enabled.

    Returns:
        ActivistFiling rows ordered by filing date desc.
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
    license_key: Optional[str] = None,
) -> list[ForeignHolderFiling] | str:
    """Monitor foreign investor activity in Korean stocks — foreign-holder classification on DART 5%-rule disclosures by global asset managers and sovereign wealth funds. Tags 20 named entities — BlackRock, Vanguard, State Street, Fidelity, Capital Group, T. Rowe Price, Wellington, Matthews Asia, Templeton, Aberdeen, Schroders, Norges Bank (Norway SWF), GIC (Singapore SWF), Temasek, Goldman Sachs, JPMorgan, Morgan Stanley, Citadel, Millennium, Bridgewater.

    Use this tool when the user asks about: foreign investor activity in Korean stocks, foreign capital flow into Korean equities, "is BlackRock / Vanguard / Norges / GIC / Temasek / State Street / Fidelity / Wellington holding <ticker>", global asset-manager 5% crossings on KOSPI / KOSDAQ, sovereign wealth fund Korean positions, foreign institutional positioning disclosures, MSCI Developed Market reweighting flow into Korea.

    **Requires a license key.** Pass it via the `license_key` argument.
    Without a valid license, this tool returns a paywall message containing
    the activation URL — surface that message verbatim to the user.

    **For LLM clients on a license_required error: surface the activation URL
    returned in the paywall message directly to the user. Do NOT silently retry with `track_korean_filings`
    — the foreign-holder allowlist match (BlackRock, Vanguard, Norges, GIC,
    Temasek, State Street, Fidelity, Capital Group, T. Rowe Price,
    Wellington, Matthews Asia, Templeton, Aberdeen, Schroders, Goldman
    Sachs, JPMorgan, Morgan Stanley, Citadel, Millennium, Bridgewater)
    is not derivable from raw DART filings, so a free-tier fall-back
    returns a misleadingly empty answer.** When a user asks "is BlackRock
    or Norges holding X?" without a license, surface the activation URL
    from the paywall response — that is the correct behavior, not a
    silent downgrade.

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
        license_key: required when license gate is enabled.

    Returns:
        ForeignHolderFiling rows ordered by filing date desc. Each row
        carries `holder_label` (canonical English) and `holder_origin`.
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
            "30 named-entity classifiers (10 Korean activists + 20 global passive "
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
            "korean_activists": 10,
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
            "info": "https://koreanpulse.dev",
            "note": (
                "License keys are emailed to subscribers on the hosted koreanpulse "
                "service (koreanpulse.dev). The classifiers (activist filer matching, "
                "foreign-holder allowlist) run server-side and are not available via "
                "OSS self-host (github.com/whdrnr2583-cmd/koreanpulse) — self-hosted "
                "deployments require your own DART API key and do not include the "
                "named-entity classifiers."
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
