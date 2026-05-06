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
    if not _require_license():
        return
    try:
        await validate_license_or_raise(license_key, cost_units=units)
    except LicenseError as exc:
        # Surface a clean, actionable error to the LLM client.
        raise RuntimeError(f"[koreanpulse:{exc.code}] {exc}") from exc


# `fill_corp_name_en` lives in `koreanpulse._enrich` so it can be
# unit-tested without importing FastMCP. The server module just calls it.


# ── Tools ───────────────────────────────────────────────────────────────────


@mcp.tool()
async def track_korean_filings(
    company_corp_code: Optional[str] = None,
    days: int = 7,
    filing_type: Optional[str] = None,
    limit: int = 30,
    translate: bool = True,
    summarize: bool = False,
    license_key: Optional[str] = None,
) -> list[Filing]:
    """Fetch recent DART filings for Korean listed companies.

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


@mcp.tool()
async def lookup_corp_code(
    query: str,
    listed_only: bool = False,
    limit: int = 10,
    license_key: Optional[str] = None,
) -> list[CorpEntry]:
    """Resolve a Korean company name (or partial name) to its DART corp code.

    Args:
        query: substring of the Korean corp name. Examples: "삼성전자", "현대차", "셀트리온".
        listed_only: if True, only return companies with a KRX stock code.
        limit: max matches to return.
        license_key: subscription key. Required when license gate is enabled.

    Returns:
        List of CorpEntry. Use the `corp_code` field as input to other tools.
    """
    await _gate(license_key, units=1)
    return await lookup_by_name(query, listed_only=listed_only, limit=limit)


@mcp.tool()
async def resolve_stock_code(
    stock_code: str,
    license_key: Optional[str] = None,
) -> Optional[CorpEntry]:
    """Resolve a 6-digit KRX stock code to its DART corp entry."""
    await _gate(license_key, units=1)
    return await lookup_by_stock_code(stock_code)


@mcp.tool()
async def search_korean_industry_news(
    industries: Optional[list[str]] = None,
    sources: Optional[list[str]] = None,
    limit: int = 20,
    translate: bool = True,
    license_key: Optional[str] = None,
) -> list[Article]:
    """Search recent Korean industry news from licensed RSS feeds.

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


@mcp.tool()
async def monitor_activist_investors(
    days: int = 14,
    company_corp_code: Optional[str] = None,
    activist_only: bool = False,
    translate: bool = True,
    limit: int = 50,
    license_key: Optional[str] = None,
) -> list[ActivistFiling]:
    """Watch DART shareholding disclosures (filing type D) for activist moves.

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
    await _gate(license_key, units=1 + (1 if activist_only else 0))

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


@mcp.tool()
async def monitor_foreign_holders(
    days: int = 14,
    company_corp_code: Optional[str] = None,
    origin: Optional[str] = None,
    translate: bool = True,
    limit: int = 50,
    license_key: Optional[str] = None,
) -> list[ForeignHolderFiling]:
    """Watch DART 5%-rule disclosures (filing type D) by global asset
    managers and sovereign wealth funds.

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
    await _gate(license_key, units=1)

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


@mcp.tool()
async def koreanpulse_about() -> dict:
    """Return basic info about this MCP server (version, available tools, sources)."""
    n_corp = 0
    try:
        n_corp = await ensure_index_loaded()
    except Exception:  # noqa: BLE001
        n_corp = -1  # not loaded yet (no API key in env)
    return {
        "name": "koreanpulse",
        "version": __version__,
        "description": (
            "Korean industry intelligence MCP for foreign fund analysts. "
            "Real-time DART filings + Korean industry news, translated to English on-demand."
        ),
        "tools_available": [
            "track_korean_filings",
            "lookup_corp_code",
            "resolve_stock_code",
            "search_korean_industry_news",
            "monitor_activist_investors",
            "monitor_foreign_holders",
            "koreanpulse_about",
        ],
        "tools_planned": [
            "digest_analyst_reports",
            "get_ma_pipeline",
            "track_government_policy",
            "summarize_korean_earnings_call",
        ],
        "corp_index_size": n_corp,
        "homepage": "https://koreanpulse.dev",
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
