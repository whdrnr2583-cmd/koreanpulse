# openbb-koreanpulse

OpenBB Platform provider extension for [koreanpulse](https://koreanpulse.dev) — English-translated Korean stock market disclosures, sourced from [DART](https://opendart.fss.or.kr/) (Korea's Financial Supervisory Service electronic disclosure system).

```python
from openbb import obb

filings = obb.equity.fundamental.filings(symbol="005930", provider="koreanpulse")
filings.to_df()
```

Returns DART filings for Samsung Electronics (KRX `005930`) with the standard OpenBB `CompanyFilings` fields (`filing_date`, `report_type`, `report_url`) plus koreanpulse's DART enrichment:

| Field | Description |
|---|---|
| `symbol` | 6-digit KRX stock code |
| `corp_name` | Company name in Korean |
| `corp_name_en` | LLM-translated company name in English, when available |
| `title` | Filing title in Korean (DART `report_nm`) |
| `receipt_no` | DART receipt number (`rcept_no`) |
| `is_correction` | `True` when the filing is a DART correction re-filing ([기재정정]/[첨부정정]) |
| `previous_receipt_no` | Receipt number of the filing this correction amends, when resolved |
| `red_flags` | Governance/distress tags inferred from the filing title (e.g. `cb_issuance`, `rights_issue`) |

## Install

```bash
pip install openbb openbb-koreanpulse
```

## Setup — DART API key

This provider needs a **DART API key** (free, from the Korean government's own disclosure system — not a koreanpulse account):

1. Sign up at <https://opendart.fss.or.kr/> (Korean-language site; a few fields, instant approval, no card).
2. Set it as `KOREANPULSE_API_KEY` in your environment, `.env` file, or OpenBB `user_settings.json`:

   ```bash
   export KOREANPULSE_API_KEY="your-dart-key"
   ```

   Note: OpenBB matches environment variables to a provider credential by
   the unprefixed `<provider>_<credential>` name (`koreanpulse_api_key` ->
   `KOREANPULSE_API_KEY`), **not** an `OPENBB_`-prefixed variant — verified
   against openbb-core 1.6.13 / openbb 4.7.2. `OPENBB_KOREANPULSE_API_KEY`
   will silently *not* wire through.

   or in Python:

   ```python
   from openbb import obb
   obb.user.credentials.koreanpulse_api_key = "your-dart-key"
   ```

No separate koreanpulse account or license key is required for this read path — it calls the open-source [`koreanpulse`](https://pypi.org/project/koreanpulse/) package's DART client directly (AGPL-3.0-or-later, source at <https://github.com/whdrnr2583-cmd/koreanpulse>).

## What this package is

A minimal adapter: one OpenBB standard model (`CompanyFilings`), one Fetcher, no extra network calls beyond what `koreanpulse.dart`/`koreanpulse.corp_code` already make. It resolves a 6-digit KRX stock code to a DART `corp_code` via `koreanpulse.corp_code.lookup_by_stock_code`, then calls `koreanpulse.dart.list_filings`, and maps the result onto OpenBB's `CompanyFilingsData` shape.

It does not add any account-management logic. koreanpulse's hosted MCP server is a separate product surface (see <https://koreanpulse.dev>) and is unrelated to this local, self-hosted read path.

## Query parameters

```python
obb.equity.fundamental.filings(
    symbol="005930",       # required — 6-digit KRX code, or e.g. "005930.KS"
    start_date="2026-01-01",  # optional, defaults to 90 days before end_date
    end_date="2026-07-01",    # optional, defaults to today
    limit=100,                 # optional, max 100 (DART's single-page cap)
    provider="koreanpulse",
)
```

## Development

```bash
pip install -e ".[test]"
pytest
```

Tests mock all DART network calls (via `koreanpulse.corp_code` / `koreanpulse.dart`) — no network access or API key required to run the suite.

## Publish (not yet done — maintainer action)

```bash
python -m build
python -m twine upload dist/*
```

## License

AGPL-3.0-or-later, matching `koreanpulse` and the OpenBB Platform itself.
