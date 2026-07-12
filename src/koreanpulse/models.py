"""Pydantic models returned by koreanpulse tools.

Public surface — these end up serialized into MCP tool responses, so changes
here are breaking changes. Keep field names stable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Article(BaseModel):
    """One Korean news article returned by `search_korean_industry_news`."""

    title_ko: str
    title_en: str = Field(description="LLM-translated English title")
    source_key: str = Field(description="Source id from sources.NEWS_SOURCES")
    source_name: str = Field(description="Korean source name for display")
    url: str
    published_at: datetime
    summary_en: str = Field(
        description="<= 200 word LLM summary in English. Always attributed."
    )
    industries: list[str] = Field(default_factory=list)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.5)
    attribution: str = Field(description="Required attribution string")
    snippet: str = Field(
        default="",
        description=(
            "~300-char plain-text excerpt from the RSS `description` field "
            "(HTML-unescaped, tags stripped, whitespace collapsed). No "
            "additional network fetch — derived from the same feed item as "
            "the title. Empty when the source's feed carries no description."
        ),
    )


class Filing(BaseModel):
    """One DART filing returned by `track_korean_filings`."""

    corp_code: str = Field(description="DART 8-digit corp code")
    corp_name_ko: str
    corp_name_en: Optional[str] = None
    stock_code: Optional[str] = Field(
        default=None, description="6-digit KRX stock code if listed"
    )
    market: Optional[str] = Field(
        default=None,
        description=(
            "Listing market from DART corp_cls: 'KOSPI', 'KOSDAQ', 'KONEX', "
            "or 'OTHER'. None when DART omits corp_cls."
        ),
    )
    filing_type: str = Field(description="DART filing type code (A–J)")
    filing_type_label_ko: str
    filing_type_label_en: str
    title: str = Field(description="Filing title (Korean)")
    red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Governance/distress tags inferred from the filing title, e.g. "
            "'cb_issuance', 'controlling_shareholder_change', 'rehabilitation', "
            "'audit_opinion', 'disclosure_violation', 'rights_issue', "
            "'capital_reduction', 'management_designation', 'delisting_risk', "
            "'trading_halt', 'reverse_split', 'short_term_borrowing', "
            "'going_concern'. Empty when no keyword matched."
        ),
    )
    title_en: Optional[str] = Field(
        default=None, description="LLM-translated title"
    )
    summary_en: Optional[str] = Field(
        default=None, description="LLM summary, only set when caller asks"
    )
    receipt_no: str = Field(description="DART receipt number; key for fetching")
    filed_at: datetime
    dart_url: str = Field(description="Human-readable DART URL")
    raw_xml_url: Optional[str] = Field(
        default=None, description="OpenAPI raw XML if applicable"
    )
    filer_name_ko: Optional[str] = Field(
        default=None,
        description=(
            "Reporting entity (DART `flr_nm`). For type-D shareholding "
            "disclosures this is typically the holder (often an activist); "
            "for periodic reports it's the company itself."
        ),
    )
    attribution: str
    holding_pct: Optional[float] = Field(
        default=None,
        description=(
            "Reporter's current holding percentage from DART majorstock.json "
            "(대량보유상황보고, `stkrt`). Paid-tier enrichment on "
            "monitor_activist_investors / monitor_foreign_holders rows only; "
            "None when not looked up or no reporter match was found."
        ),
    )
    holding_pct_change: Optional[float] = Field(
        default=None,
        description=(
            "Change in holding percentage versus the prior majorstock "
            "report (`stkrt_irds`). Same paid-tier enrichment as `holding_pct`."
        ),
    )
    holder_reporter_ko: Optional[str] = Field(
        default=None,
        description=(
            "DART majorstock reporter name (`repror`) matched to this "
            "filing's filer. Same paid-tier enrichment as `holding_pct`."
        ),
    )
    query_total_count: Optional[int] = Field(
        default=None,
        description=(
            "DART's reported total_count for the query that produced this "
            "filing — the full match count before `limit`/`page_count` "
            "truncation, not the number of rows returned. None on cached "
            "rows written before this field existed."
        ),
    )
    data_fetched_at: Optional[datetime] = Field(
        default=None,
        description=(
            "UTC timestamp this filing was live-fetched from DART (as-of "
            "time for the data). None for rows served from a cache entry "
            "written before this field existed."
        ),
    )


class ActivistFiling(Filing):
    """A type-D filing flagged with activist-investor heuristics."""

    is_likely_activist: bool = Field(
        default=False,
        description="Filer name matched a known Korean activist allowlist.",
    )
    activist_label: Optional[str] = Field(
        default=None,
        description="Canonical activist name if matched (e.g. 'KCGI', 'Align Partners').",
    )


class ForeignHolderFiling(Filing):
    """A type-D filing matched against the foreign-passive-holder allowlist.

    Used as a leading indicator of foreign capital flow into a Korean
    ticker. Distinct from `ActivistFiling` because passive holders
    (BlackRock, Vanguard, SWFs) signal allocation rather than governance
    pressure.
    """

    holder_label: str = Field(
        description="Canonical English holder name (e.g. 'BlackRock', 'Norges Bank (Norway SWF)').",
    )
    holder_origin: str = Field(
        description="Holder origin: 'us', 'uk', 'eu', 'other', or 'kr' (rare).",
    )
