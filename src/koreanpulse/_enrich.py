"""Filing-enrichment helpers, separated from server.py so they can be
unit-tested without spinning up FastMCP at import time.

Each helper takes a list of Filing-shaped objects and a Translator,
mutates the rows in place, and never raises — translation failures get
logged and the row is left without the enrichment field. Tools call
these from inside their main flow when `translate=True`.
"""
from __future__ import annotations

import logging

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
