"""Watchlist → alert foundation (internal, feature-flagged, design-partner scope).

This is the smallest vertical slice of the planned watchlist-alert product:
"track Korean companies and receive material DART events in English without
checking manually." It is NOT exposed as an MCP tool and is disabled by
default — set ``KOREANPULSE_WATCHLIST_ENABLED=1`` to allow the polling
entrypoint to run. One delivery channel (the existing ``koreanpulse.alerts``
webhook primitive — Discord for the internal design-partner test).

Design notes (kept deliberately minimal):

* **Store** — a local JSON file (``KOREANPULSE_WATCHLIST_STATE`` env, default
  ``~/.koreanpulse/watchlists.json``), written atomically. One design partner
  does not need a database; the record shape is chosen so it can be lifted
  into D1/Postgres unchanged when the product ships.
* **Idempotency** — ``delivered_receipts`` is the ledger. A receipt number is
  added ONLY after its alert was delivered successfully, so a delivery
  failure is retried on the next poll and the same filing is never delivered
  twice to the same watchlist.
* **Checkpoint** — ``last_checked`` bounds the fetch window and only advances
  when every company in the watchlist was fetched without error; a partial
  fetch failure is reported in ``PollResult.errors`` (never silently
  skipped) and re-covered next poll.
* **Materiality** — reuses existing product logic only: ``Filing.red_flags``
  (title-keyword tags), and 5%-rule type-D filings whose filer matches the
  maintained activist/foreign-holder allowlist (``activists.match_investor``).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .activists import match_investor
from .alerts import AlertResult, send_alert
from .dart import list_filings
from .models import Filing

logger = logging.getLogger(__name__)

MAX_CORP_CODES = 10
MAX_ALERTS_PER_COMPANY = 5
# How far past last_checked we re-scan, to absorb late-indexed filings.
LOOKBACK_MARGIN_DAYS = 1
# Ledger bound per company — old receipts age out far after their window.
MAX_LEDGER_PER_COMPANY = 200

NOT_ADVICE_FOOTER = "Not investment advice — disclosure data only."


def watchlist_enabled() -> bool:
    return os.environ.get("KOREANPULSE_WATCHLIST_ENABLED", "0") == "1"


@dataclass
class Watchlist:
    """One user's watchlist. ``owner`` is an email or opaque identifier."""

    id: str
    owner: str
    corp_codes: list[str]
    channel_url: str
    enabled: bool = True
    last_checked: Optional[str] = None  # ISO date (yyyy-mm-dd)
    delivered_receipts: dict[str, list[str]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if len(self.corp_codes) > MAX_CORP_CODES:
            raise ValueError(f"a watchlist holds at most {MAX_CORP_CODES} corp codes")
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class MaterialEvent:
    corp_code: str
    filing: Filing
    category: str        # "red_flag:<tag>[,..]" | "activist:<name>" | "foreign:<name>"
    why: str             # human sentence explaining the match


@dataclass
class PollResult:
    watchlist_id: str
    delivered: list[str] = field(default_factory=list)   # receipt numbers
    failed: list[str] = field(default_factory=list)      # delivery failures (receipts)
    errors: dict[str, str] = field(default_factory=dict)  # corp_code -> fetch error
    skipped_duplicates: int = 0
    checkpoint_advanced: bool = False


# ── store ────────────────────────────────────────────────────────────────

def _state_path() -> Path:
    return Path(
        os.environ.get(
            "KOREANPULSE_WATCHLIST_STATE",
            str(Path.home() / ".koreanpulse" / "watchlists.json"),
        )
    )


def load_watchlists(path: Optional[Path] = None) -> list[Watchlist]:
    p = path or _state_path()
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [Watchlist(**item) for item in raw]


def save_watchlists(watchlists: list[Watchlist], path: Optional[Path] = None) -> None:
    """Atomic write — a crash mid-save never corrupts the ledger."""
    p = path or _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([w.__dict__ for w in watchlists], ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".watchlists-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ── materiality (existing product logic only) ────────────────────────────

def classify_material(filing: Filing) -> Optional[MaterialEvent]:
    """Return a MaterialEvent when the filing matters, else None.

    Material =
      * any red-flag tag on the title (existing ``tag_red_flags`` output), or
      * a type-D (5%-rule family) filing whose filer matches the maintained
        activist / foreign-holder allowlist.
    Nothing is guessed: unmatched filers and untagged titles are not material.
    """
    if filing.red_flags:
        tags = ",".join(filing.red_flags)
        return MaterialEvent(
            corp_code=filing.corp_code,
            filing=filing,
            category=f"red_flag:{tags}",
            why=f"Filing title matched red-flag keyword tag(s): {tags}.",
        )
    if filing.filing_type == "D" and filing.filer_name_ko:
        m = match_investor(filing.filer_name_ko)
        if m is not None:
            klass = m.klass.value
            return MaterialEvent(
                corp_code=filing.corp_code,
                filing=filing,
                category=f"{klass}:{m.canonical}",
                why=(
                    f"5%-rule filer of record '{filing.filer_name_ko}' matched the "
                    f"maintained allowlist entry '{m.canonical}' ({klass})."
                ),
            )
    return None


def format_alert(event: MaterialEvent, title_en: Optional[str]) -> tuple[str, str]:
    """(title, body) for the alert channel. English title is best-effort."""
    f = event.filing
    head = f"{f.corp_name_ko} ({f.stock_code or f.corp_code}) — {event.category}"
    lines = [
        f"Filing: {f.title}",
    ]
    if title_en:
        lines.append(f"English: {title_en}")
    lines += [
        f"Filed: {f.filed_at}",
        f"Why matched: {event.why}",
        f"DART receipt: {f.receipt_no}",
        f"Source: {f.dart_url}",
        NOT_ADVICE_FOOTER,
    ]
    return head, "\n".join(lines)


# ── polling ──────────────────────────────────────────────────────────────

FetchFn = Callable[..., Awaitable[list[Filing]]]
SendFn = Callable[..., Awaitable[AlertResult]]
TranslateFn = Callable[[str], Awaitable[str]]


async def poll_watchlist(
    wl: Watchlist,
    *,
    today: Optional[date] = None,
    fetch: FetchFn = list_filings,
    send: SendFn = send_alert,
    translate: Optional[TranslateFn] = None,
) -> PollResult:
    """One incremental poll of one watchlist. Pure orchestration; every
    dependency is injectable for tests."""
    result = PollResult(watchlist_id=wl.id)
    if not wl.enabled:
        return result

    end = today or datetime.now(timezone.utc).date()
    if wl.last_checked:
        start = date.fromisoformat(wl.last_checked) - timedelta(days=LOOKBACK_MARGIN_DAYS)
    else:
        # First poll: look back a week so the partner sees a non-empty result.
        start = end - timedelta(days=7)

    for corp_code in wl.corp_codes:
        try:
            filings = await fetch(corp_code=corp_code, bgn_de=start, end_de=end)
        except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
            result.errors[corp_code] = f"{type(exc).__name__}: {exc}"
            logger.error("[watchlist %s] fetch failed for %s: %s", wl.id, corp_code, exc)
            continue

        ledger = wl.delivered_receipts.setdefault(corp_code, [])
        sent_this_company = 0
        for filing in sorted(filings, key=lambda f: (f.filed_at, f.receipt_no)):
            event = classify_material(filing)
            if event is None:
                continue
            if filing.receipt_no in ledger:
                result.skipped_duplicates += 1
                continue
            if sent_this_company >= MAX_ALERTS_PER_COMPANY:
                # Leave the rest undelivered; the ledger keeps them pending
                # for the next poll instead of dropping them.
                break

            title_en: Optional[str] = None
            if translate is not None:
                try:
                    title_en = await translate(filing.title)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[watchlist %s] translate failed for %s (alert falls back to Korean): %s",
                        wl.id, filing.receipt_no, type(exc).__name__,
                    )

            title, body = format_alert(event, title_en)
            delivery = await send(wl.channel_url, title=title, body=body)
            if delivery.ok:
                ledger.append(filing.receipt_no)
                del ledger[:-MAX_LEDGER_PER_COMPANY]
                result.delivered.append(filing.receipt_no)
                sent_this_company += 1
            else:
                # Do NOT record the receipt — it will be retried next poll.
                result.failed.append(filing.receipt_no)
                logger.error(
                    "[watchlist %s] delivery failed for %s (will retry next poll)",
                    wl.id, filing.receipt_no,
                )

    # Advance the checkpoint only when every company was fetched cleanly and
    # nothing is stuck undelivered — a failed delivery keeps the window open.
    if not result.errors and not result.failed:
        wl.last_checked = end.isoformat()
        result.checkpoint_advanced = True
    wl.updated_at = datetime.now(timezone.utc).isoformat()
    return result


async def run_polling(path: Optional[Path] = None) -> list[PollResult]:
    """Entry point for an operator-run poll (cron / manual). Feature-flagged."""
    if not watchlist_enabled():
        raise RuntimeError(
            "watchlist polling is disabled — set KOREANPULSE_WATCHLIST_ENABLED=1 "
            "(internal design-partner feature, off by default)"
        )
    watchlists = load_watchlists(path)
    results = []
    for wl in watchlists:
        if wl.enabled:
            results.append(await poll_watchlist(wl))
    save_watchlists(watchlists, path)
    return results
