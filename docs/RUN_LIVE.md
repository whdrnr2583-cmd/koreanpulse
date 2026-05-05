# Run koreanpulse live (with real DART data)

Step-by-step to verify the build against the real DART API.

## 0. Prereq

```bash
cd C:/Users/whdrn/claudeCode/koreanpulse
pip install -e ".[test]"
```

## 1. Set env vars

PowerShell:

```powershell
$env:DART_API_KEY = "your-40-char-dart-key"
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # optional, for translation
```

bash:

```bash
export DART_API_KEY=your-40-char-dart-key
export ANTHROPIC_API_KEY=sk-ant-...     # optional
```

## 2. Run the quickstart

```bash
python examples/quickstart.py
```

The first run will download the DART corp index (~5MB) into `.data/dart/`.
Subsequent runs hit that cache (refreshes every 7 days).

## 3. Run the MCP server

```bash
koreanpulse
```

Listens on stdio. To test interactively, point Claude Desktop at it (see
`CLAUDE_DESKTOP.md`).

## 4. Sanity-check via Python REPL

```python
import asyncio
from koreanpulse.dart import list_filings
from datetime import date, timedelta

async def main():
    end = date.today()
    bgn = end - timedelta(days=3)
    filings = await list_filings(bgn_de=bgn, end_de=end, page_count=10)
    for f in filings:
        print(f.filed_at.date(), f.corp_name_ko, "-", f.title)

asyncio.run(main())
```

## 5. What to watch in production

- Translation cache hit rate: read `.data/cache/translate.jsonl` line count growth.
  After a few days it should grow slowly (most filings are repeats).
- Cost ledger: `.data/cost.jsonl`. One line per LLM call.
- DART throttle: agentprod's bucket caps at 5 req/s. Burst protection is in.

## 6. Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `DART_API_KEY env var is missing` | env not exported in this shell | re-export |
| `DART 020: quota exceeded` | DART daily quota | wait until midnight KST or get a second key |
| `ANTHROPIC_API_KEY missing` | translate=True called without key | set env or pass `translate=False` |
| Empty `corp_code` index | DART corpCode.xml fetch failed | retry; check key validity at https://opendart.fss.or.kr/ |
