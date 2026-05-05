# CI / release pipeline

Two workflows in `.github/workflows/`:

## `ci.yml` — runs on every push + PR to `main`

- Matrix: Python 3.10 / 3.11 / 3.12
- `pytest` + `ruff check`
- Builds sdist + wheel as a sanity check (uploaded as artifact, 7d retention)

`agentprod` is a path dep, which CI doesn't have by default. The workflow
clones it from GitHub into `../agentprod`, falling back to a tiny stub if
the repo is still private.

## `release.yml` — runs on `v*.*.*` git tags

- Builds dist
- Verifies tag matches `pyproject.toml` `[project].version`
- Publishes to PyPI via **trusted publishing** (no API token in repo)
- Creates a GitHub release with auto-generated notes

### One-time PyPI trusted publishing setup

1. Create an account on <https://pypi.org/> (if not already)
2. Reserve the `koreanpulse` project name by uploading manually once
   *or* request a project name (PyPI will allow first publish via trusted
   publisher if the name is available)
3. On PyPI: **Your projects → koreanpulse → Publishing → Add a new pending
   publisher**
   - Owner: `whdrnr2583-cmd`
   - Repository name: `koreanpulse`
   - Workflow filename: `release.yml`
   - Environment name: `pypi`
4. On GitHub: **Settings → Environments → New environment → `pypi`**
   - Optional: add required reviewers so a release tag still needs your manual
     approval before it pushes to PyPI

After that, every `git push origin v0.1.0` cleanly publishes.

### Cutting a release

```bash
# Update version in pyproject.toml first, then:
git commit -am "release v0.1.0"
git tag v0.1.0
git push origin main --tags
```

The `release` workflow takes ~2 minutes end-to-end.
