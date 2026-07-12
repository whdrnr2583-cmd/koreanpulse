"""Filing-enrichment helpers, separated from server.py so they can be
unit-tested without spinning up FastMCP at import time.

Each helper takes a list of Filing-shaped objects and a Translator,
mutates the rows in place, and never raises — translation failures get
logged and the row is left without the enrichment field. Tools call
these from inside their main flow when `translate=True`.
"""
from __future__ import annotations

import logging
from typing import Optional

from koreanpulse.dart import MajorHolding, list_major_holdings
from koreanpulse.translate import Translator

logger = logging.getLogger(__name__)


async def fill_corp_name_en(
    filings: list,
    translator: Translator,
    *,
    op: str,
) -> None:
    """Fill `corp_name_en` on each filing using the shared cache.

    Same Korean corp_name → same translation across filings; the cache
    absorbs duplicates (within a batch and across batches). Cost is
    negligible: ~5 tokens × 1 LLM call per unique Korean name, then
    cached forever. Failures are logged and skipped — never blocks
    the response.

    Args:
        filings: Filing-shaped objects with corp_name_ko / corp_name_en.
        translator: explicit Translator. Caller passes the same instance
                    used for title translation in the same tool invocation.
        op: label string for cost-tracking (e.g. tool name).
    """
    seen: dict[str, str] = {}  # corp_code → en (intra-batch dedup)
    for f in filings:
        if f.corp_name_en or not f.corp_name_ko:
            continue
        if f.corp_code and f.corp_code in seen:
            f.corp_name_en = seen[f.corp_code]
            continue
        try:
            en = await translator.translate_corp_name(
                f.corp_name_ko, labels={"tool": op}
            )
            if en:
                f.corp_name_en = en
                if f.corp_code:
                    seen[f.corp_code] = en
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "corp_name_en translate failed for %s (%s): %s",
                f.corp_name_ko, f.corp_code, exc,
            )


def _best_holding_match(
    filer_name_ko: Optional[str], holdings: list[MajorHolding]
) -> Optional[MajorHolding]:
    """Match a filing's filer name against DART majorstock reporter names.

    Exact string match first; falls back to substring containment in
    either direction (e.g. a filer name carrying a suffix like "외 1인"
    that the majorstock `repror` doesn't, or vice versa). Returns None on
    no match — callers must not fabricate a match.
    """
    if not filer_name_ko:
        return None
    for h in holdings:
        if h.repror == filer_name_ko:
            return h
    for h in holdings:
        if h.repror in filer_name_ko or filer_name_ko in h.repror:
            return h
    return None


async def fill_holding_pct(
    filings: list,
    *,
    op: str,
    max_corp_codes: int = 8,
) -> None:
    """Fill `holding_pct` / `holding_pct_change` / `holder_reporter_ko` on
    already-matched activist/foreign-holder filings using DART's
    majorstock feed.

    Callers pass only the subset of rows they've already flagged as a
    match (e.g. `is_likely_activist` rows for `monitor_activist_investors`,
    or the full list for `monitor_foreign_holders` since every row there
    is already a foreign-holder match) — this function does not itself
    decide which rows are "matched".

    Non-throwing: a DART/network failure for one corp_code is logged and
    skipped, leaving that corp's rows unenriched (fields stay None)
    rather than failing the whole tool call. Caps distinct corp_code
    lookups at `max_corp_codes` to bound DART-quota spend per tool call.

    Args:
        filings: Filing-shaped objects with corp_code / filer_name_ko /
            holding_pct / holding_pct_change / holder_reporter_ko.
        op: label string for logging (e.g. tool name).
        max_corp_codes: cap on distinct corp_code lookups per call.
    """
    unique_codes: list[str] = []
    for f in filings:
        if f.corp_code and f.corp_code not in unique_codes:
            unique_codes.append(f.corp_code)
    unique_codes = unique_codes[:max_corp_codes]

    for corp_code in unique_codes:
        try:
            holdings = await list_major_holdings(corp_code)
        except Exception as exc:  # noqa: BLE001 — never block the response
            logger.warning(
                "majorstock enrich failed for corp_code=%s (%s): %s",
                corp_code, op, exc,
            )
            continue
        if not holdings:
            continue
        for f in filings:
            if f.corp_code != corp_code:
                continue
            match = _best_holding_match(f.filer_name_ko, holdings)
            if match is None:
                continue
            f.holding_pct = match.stkrt
            f.holding_pct_change = match.stkrt_irds
            f.holder_reporter_ko = match.repror
