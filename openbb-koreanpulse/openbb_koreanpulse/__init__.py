"""koreanpulse provider module for the OpenBB Platform.

Registers `koreanpulse` as an OpenBB provider extension exposing one standard
model — `CompanyFilings` — backed by DART (Korea's Financial Supervisory
Service electronic disclosure system), via the `koreanpulse` package
(https://pypi.org/project/koreanpulse/, https://koreanpulse.dev).

Requires a free DART API key (https://opendart.fss.or.kr/) set as
`KOREANPULSE_API_KEY` — see this package's README for setup.
"""

from openbb_core.provider.abstract.provider import Provider

from openbb_koreanpulse.models.company_filings import KoreanpulseCompanyFilingsFetcher

koreanpulse_provider = Provider(
    name="koreanpulse",
    website="https://koreanpulse.dev",
    description=(
        "Koreanpulse translates Korean stock market disclosures from DART "
        "(the Financial Supervisory Service's Korean-language electronic "
        "disclosure system) into English, with correction-filing lineage "
        "and title-derived governance/distress tags layered on top of the "
        "raw DART feed. Open source (AGPL-3.0-or-later), self-hosted by the "
        "caller. Requires a free DART API key from "
        "https://opendart.fss.or.kr/."
    ),
    credentials=["api_key"],
    fetcher_dict={
        "CompanyFilings": KoreanpulseCompanyFilingsFetcher,
    },
    repr_name="Koreanpulse (Korean DART Disclosures)",
    instructions=(
        "1. Get a free API key at https://opendart.fss.or.kr/ (Korean sign-up, "
        "instant approval, no card required).\n"
        "2. Set it as `KOREANPULSE_API_KEY` in your environment / `.env` "
        "(OpenBB matches env vars by the unprefixed `<provider>_<credential>` "
        "name, not `OPENBB_`-prefixed), or pass it via "
        "`obb.user.credentials.koreanpulse_api_key = \"...\"`.\n"
        "3. Note: this is a DART API key, not a koreanpulse account — "
        "openbb-koreanpulse itself requires no separate signup or key."
    ),
)
