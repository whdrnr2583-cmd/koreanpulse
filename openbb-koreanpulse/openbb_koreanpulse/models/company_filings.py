"""Koreanpulse Company Filings Model.

Thin adapter over the `koreanpulse` package's DART client — one read path:
symbol (6-digit KRX stock code) -> DART corp_code -> `list.json` filings.
No koreanpulse core logic is duplicated here; all resolution, parsing, and
title-derived tagging happens inside `koreanpulse.corp_code` /
`koreanpulse.dart`, which this Fetcher calls directly.
"""

# pylint: disable=unused-argument

from datetime import (
    date as dateType,
    timedelta,
)
from typing import Any

from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_filings import (
    CompanyFilingsData,
    CompanyFilingsQueryParams,
)
from openbb_core.provider.utils.descriptions import QUERY_DESCRIPTIONS
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator


class KoreanpulseCompanyFilingsQueryParams(CompanyFilingsQueryParams):
    """Koreanpulse Company Filings Query.

    Source: https://opendart.fss.or.kr/ (DART — Korea's Financial Supervisory
    Service electronic disclosure system), via https://koreanpulse.dev.
    """

    symbol: str = Field(
        description=(
            "6-digit Korean Exchange (KRX) stock code, e.g. '005930' for "
            "Samsung Electronics. Required — this provider does not support "
            "an all-companies query."
        )
    )
    start_date: dateType | None = Field(
        default=None,
        description=QUERY_DESCRIPTIONS.get("start_date", "")
        + " Defaults to 90 days before end_date.",
    )
    end_date: dateType | None = Field(
        default=None,
        description=QUERY_DESCRIPTIONS.get("end_date", "") + " Defaults to today.",
    )
    limit: int = Field(
        default=100,
        le=100,
        gt=0,
        description=(
            "Max number of filings to return. DART caps a single page at "
            "100 — this provider does not paginate beyond that."
        ),
    )

    @field_validator("symbol", mode="before", check_fields=False)
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Normalize to DART's 6-digit stock-code format.

        Delegates to `koreanpulse.corp_code.normalize_stock_code` — strips
        whitespace, drops a trailing `.KS`/`.KQ`/`.KRX` suffix, and
        zero-pads a short numeric code (e.g. "5930" -> "005930").
        """
        if not v:
            raise ValueError("symbol is required (6-digit KRX stock code).")
        # pylint: disable=import-outside-toplevel
        from koreanpulse.corp_code import normalize_stock_code

        return normalize_stock_code(str(v))


class KoreanpulseCompanyFilingsData(CompanyFilingsData):
    """Koreanpulse Company Filings Data.

    Extra fields carry koreanpulse's DART enrichment — Korean-language
    title, correction-filing lineage, and title-derived governance/distress
    tags — all computed from the same `list.json` call as the standard
    fields, no additional network round-trip.
    """

    symbol: str = Field(description="6-digit KRX stock code.")
    corp_name: str = Field(description="Company name in Korean (DART corp_name).")
    corp_name_en: str | None = Field(
        default=None,
        description="LLM-translated company name in English, when available.",
    )
    title: str = Field(description="Filing title in Korean (DART report_nm).")
    receipt_no: str = Field(description="DART receipt number (rcept_no).")
    is_correction: bool = Field(
        default=False,
        description=(
            "True when this filing is a DART correction re-filing "
            "([기재정정] content correction or [첨부정정] attachment correction)."
        ),
    )
    previous_receipt_no: str | None = Field(
        default=None,
        description=(
            "Receipt number of the filing this correction amends, when "
            "resolved from the same query window. None if unresolved."
        ),
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Governance/distress tags inferred from the filing title, e.g. "
            "'cb_issuance', 'rights_issue', 'audit_opinion'. Empty when no "
            "keyword matched."
        ),
    )


class KoreanpulseCompanyFilingsFetcher(
    Fetcher[
        KoreanpulseCompanyFilingsQueryParams,
        list[KoreanpulseCompanyFilingsData],
    ]
):
    """Koreanpulse Company Filings Fetcher."""

    @staticmethod
    def transform_query(
        params: dict[str, Any],
    ) -> KoreanpulseCompanyFilingsQueryParams:
        """Transform the query params, filling in the default date window."""
        transformed = KoreanpulseCompanyFilingsQueryParams(**params)
        if transformed.end_date is None:
            transformed.end_date = dateType.today()
        if transformed.start_date is None:
            transformed.start_date = transformed.end_date - timedelta(days=90)
        return transformed

    @staticmethod
    async def aextract_data(
        query: KoreanpulseCompanyFilingsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Resolve the stock code to a DART corp_code and fetch filings.

        The DART key travels through OpenBB's standard credential plumbing
        as `koreanpulse_api_key` (`KOREANPULSE_API_KEY` env var — OpenBB
        matches env vars by the unprefixed `<provider>_<credential>` name,
        not an `OPENBB_`-prefixed one) and is injected into `DART_API_KEY`,
        which is what `koreanpulse.dart` / `koreanpulse.corp_code` read
        internally — koreanpulse itself has no notion of an OpenBB
        credential, so this is the adapter's job, not koreanpulse core's.
        """
        # pylint: disable=import-outside-toplevel
        import os

        from koreanpulse.corp_code import CorpCodeError, lookup_by_stock_code
        from koreanpulse.dart import DartError, list_filings

        api_key = (credentials or {}).get("koreanpulse_api_key", "")
        if api_key:
            os.environ.setdefault("DART_API_KEY", api_key)
        if not os.environ.get("DART_API_KEY", "").strip():
            raise OpenBBError(
                "Missing DART API key. Set KOREANPULSE_API_KEY (unprefixed — "
                "not OPENBB_KOREANPULSE_API_KEY) to a free key from "
                "https://opendart.fss.or.kr/, via your .env file, "
                "user_settings.json, or obb.user.credentials.koreanpulse_api_key. "
                "See https://koreanpulse.dev for setup."
            )

        try:
            entry = await lookup_by_stock_code(query.symbol)
        except CorpCodeError as exc:
            raise OpenBBError(f"DART corp_code lookup failed: {exc}") from exc
        if entry is None:
            raise OpenBBError(
                f"No DART corp_code found for KRX stock code {query.symbol!r}."
            )

        try:
            filings = await list_filings(
                corp_code=entry.corp_code,
                bgn_de=query.start_date,
                end_de=query.end_date,
                page_count=query.limit,
            )
        except DartError as exc:
            raise OpenBBError(f"DART list_filings call failed: {exc}") from exc

        return [f.model_dump(mode="json") for f in filings]

    @staticmethod
    def transform_data(
        query: KoreanpulseCompanyFilingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[KoreanpulseCompanyFilingsData]:
        """Transform koreanpulse `Filing` rows into the standard shape."""
        if not data:
            raise EmptyDataError(
                f"No DART filings found for {query.symbol!r} between "
                f"{query.start_date} and {query.end_date}."
            )
        results = [
            KoreanpulseCompanyFilingsData(
                symbol=query.symbol,
                filing_date=row["filed_at"],
                report_type=row.get("filing_type_label_en"),
                report_url=row["dart_url"],
                corp_name=row.get("corp_name_ko", ""),
                corp_name_en=row.get("corp_name_en"),
                title=row.get("title", ""),
                receipt_no=row.get("receipt_no", ""),
                is_correction=row.get("is_correction", False),
                previous_receipt_no=row.get("previous_receipt_no"),
                red_flags=row.get("red_flags") or [],
            )
            for row in data
        ]
        return results[: query.limit]
