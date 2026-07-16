# koreanpulse — MCP server container for Glama / Smithery / general MCP hosting.
# Builds the published koreanpulse package from PyPI so Glama's
# introspection check (MCP `tools/list` over stdio) starts in seconds.
#
# Required at runtime:
#   DART_API_KEY        — https://opendart.fss.or.kr/ (free, 40k/day)
# Optional:
#   OPENAI_API_KEY      — for English translation/summarization
#   KOREANPULSE_LICENSE_KEY — required for paid-tier tools
#                              (monitor_activist_investors, monitor_foreign_holders)

FROM python:3.11-slim

WORKDIR /app

# Keep this pin at the latest version actually published to PyPI. It lagged at
# 0.1.3 — a version that was never published — so this build was failing
# outright. Bump it as part of the PyPI release step, not the source bump:
# 0.1.12/0.1.13 exist in git but are not on PyPI yet.
RUN pip install --no-cache-dir koreanpulse==0.1.11

# stdio MCP — Glama / Claude Desktop / Cursor speak JSON-RPC on stdin/stdout.
ENTRYPOINT ["koreanpulse"]
