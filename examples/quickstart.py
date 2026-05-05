"""koreanpulse quickstart — runs against the real DART API.

Prereqs:
    pip install -e ".[test]"
    # set DART_API_KEY (and optionally ANTHROPIC_API_KEY) in .env or env vars

Run:
    python examples/quickstart.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date, timedelta

# Windows console defaults to cp949; force UTF-8 so Korean prints correctly.
# (No-op on macOS/Linux which already default to UTF-8.)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

from agentprod import CostTracker
from koreanpulse.cache import FileCache
from koreanpulse.corp_code import lookup_by_name
from koreanpulse.dart import list_filings
from koreanpulse.news import fetch_industry_news
from koreanpulse.translate import Translator


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    log = logging.getLogger("quickstart")

    if not os.environ.get("DART_API_KEY"):
        log.error("DART_API_KEY env var missing — get one at https://opendart.fss.or.kr/")
        return

    # 1) Resolve a Korean company name → DART corp_code
    print("\n=== 1. lookup_corp_code('삼성전자') ===")
    matches = await lookup_by_name("삼성전자", listed_only=True, limit=3)
    for m in matches:
        print(f"  {m.corp_code} | {m.corp_name} | KRX={m.stock_code}")

    if not matches:
        log.error("no corp_code matches found")
        return
    samsung = matches[0]

    # 2) Get recent filings for Samsung
    print(f"\n=== 2. recent filings for {samsung.corp_name} ===")
    end = date.today()
    bgn = end - timedelta(days=14)
    filings = await list_filings(corp_code=samsung.corp_code, bgn_de=bgn, end_de=end)
    for f in filings[:5]:
        print(f"  [{f.filed_at.date()}] {f.filing_type_label_en}: {f.title}")
    print(f"  (total: {len(filings)})")

    # 3) Translate the first 3 filing titles via server-side LLM (if key present)
    # Use the same provider selection logic as the production Translator: respect
    # KOREANPULSE_TRANSLATE_PROVIDER env (default "openai"), then check the
    # corresponding API key.
    provider = os.environ.get("KOREANPULSE_TRANSLATE_PROVIDER", "openai").lower()
    provider_key_env = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"

    if os.environ.get(provider_key_env) and filings:
        print(f"\n=== 3. translate first 3 filings (provider={provider}, cached) ===")
        cache = FileCache(root=".data/cache")
        cost = CostTracker(jsonl_path=".data/cost.jsonl")
        translator = Translator(cache=cache, cost_tracker=cost)
        for f in filings[:3]:
            f.title_en = await translator.translate_ko_to_en(
                f.title, labels={"tenant": "quickstart"}
            )
            print(f"  {f.title}")
            print(f"    -> {f.title_en}")
        print(f"\n  cost so far: ${cost.total_usd():.6f}")
        print(f"  by op:    {cost.by_label('op')}")
        print(f"  by model: {cost.by_model()}")
    else:
        print(f"\n=== 3. translation skipped (set {provider_key_env} to enable) ===")

    # 4) Korean industry news (semiconductor + battery)
    print("\n=== 4. recent industry news (semiconductor + battery) ===")
    articles = await fetch_industry_news(
        industries=["semiconductor", "battery"], limit=5
    )
    for a in articles:
        print(f"  [{a.source_name}] {a.title_ko}")
        print(f"    tags: {a.industries}, link: {a.url}")

    print("\nDone. Cache + cost ledger persisted under .data/")


if __name__ == "__main__":
    asyncio.run(main())
