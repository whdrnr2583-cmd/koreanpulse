# Contributing

Indie-built, AGPL-licensed. PRs welcome especially for:

- New Korean primary sources (RSS feeds, public APIs)
- New industry classifier keywords (`koreanpulse.news.INDUSTRY_KEYWORDS`)
- New activist allowlist entries (`koreanpulse.activists.KOREAN_ACTIVISTS`)
- New filing-type heuristics (`_TITLE_TO_TYPE` in `dart.py`)
- Additional MCP tools that fit the "Korean primary sources, English
  output, real-time" niche

Out of scope (won't merge):

- Investment advice features (regulatory risk, see SPEC.md)
- Spatial / mapping data (Korean 공간정보관리법, see SPEC.md)
- Bypasses for source-site rate limits or paywalls

## Dev setup

You need:
- Python 3.10+
- `agentprod` checked out next to this repo (path dep in pyproject.toml).
  Either clone <https://github.com/whdrnr2583-cmd/agentprod> as
  `../agentprod`, or comment out the path source in `pyproject.toml`
  while you work on koreanpulse alone.

```bash
git clone https://github.com/whdrnr2583-cmd/koreanpulse
cd koreanpulse
python -m venv .venv && source .venv/bin/activate     # or .venv\Scripts\activate
pip install -e '.[dev]'
cp .env.example .env                                   # add your DART key
pytest -q                                              # should pass
```

## Running the live demo

```bash
# .env must contain DART_API_KEY (and optionally OPENAI_API_KEY)
python examples/quickstart.py
```

Hits real DART. First run downloads the corp-code index (~5 MB, cached 7d).

## Tests

- `pytest -q` runs the full suite (433 tests + 1 skipped without a live Postgres)
- New code should ship with tests in `tests/` matching the existing style:
  one file per module, classes for grouping, `@pytest.mark.asyncio` for
  coroutines.
- DART HTTP code uses `httpx.MockTransport` in tests — no live API access
  required for CI.
- Postgres tests in `test_license_postgres.py` are skipped automatically
  unless `DATABASE_URL_TEST` is set.

## Lint / style

```bash
ruff check src tests
```

`pyproject.toml` pins line length 100, target Python 3.10. We don't run a
formatter (deliberately — we write code that reads fluently, not code
shaped by a formatter).

## Commit style

Conventional-commits-ish, but loose. Imperative mood. Ship small commits
that read in `git log` like a story:

```
add monitor_activist_investors tool
fix quota guard test brittle on KST rollover
docs: expand BETA.md with crypto-native channels
```

## What "ship-ready" means

A change is ship-ready when:

1. `pytest -q` passes
2. `ruff check src tests` passes
3. Any user-visible API change updates `CHANGELOG.md` under `[Unreleased]`
4. Any new module gets a top-of-file docstring + a one-line entry in
   `docs/INDEX.md`
5. If the change touches MCP tools, `koreanpulse_about()` in `server.py`
   reflects the new tool list, and `smithery.yaml` + `docs/listings/*.md`
   are updated together
6. If the change touches the LicenseStore Protocol, both the in-memory
   and Postgres implementations are updated and tested

## Releasing (maintainer only)

See `docs/CI.md`. tl;dr:

```bash
# Bump version in pyproject.toml, update CHANGELOG.md
# Substitute v<NEW_VERSION> (e.g., v0.2.0).
git commit -am "release v<NEW_VERSION>"
git tag v<NEW_VERSION>
git push origin main --tags
```

The `release.yml` workflow does PyPI publish via trusted publishing
(no token in repo) and creates a GitHub release.

## Security disclosure

For anything sensitive (auth bypass, license-key leak, webhook signature
flaw), please **don't open a public issue**. Email `whdrnr2583@gmail.com`
or DM me — I'll patch and credit you.

## License

AGPL-3.0 source. Hosted service is commercial, separate license. By
submitting a PR you agree your contribution is licensed AGPL-3.0 along
with the rest of the source.
