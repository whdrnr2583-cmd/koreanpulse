/**
 * Snapshot freshness — Korea-business-day aware.
 *
 * The daily build runs on the weekday cron (KST 16:30 / UTC 07:30), so the
 * newest snapshot a visitor should ever expect is "the most recent weekday
 * whose build window has passed". A simplistic 24-hour rule marks every
 * weekend as a failure; this module instead answers "which snapshot date is
 * the freshest one that can exist right now?" and compares.
 *
 * Documented limitation: Korean public holidays are treated like normal
 * weekdays. That is safe in practice because the cron fires on every weekday
 * regardless of market holidays — DART simply returns few/no filings and the
 * build still writes a (quiet) snapshot for that date. We deliberately do NOT
 * ship a hand-maintained holiday calendar (stale calendars create the exact
 * false-confidence problem this module exists to fix).
 */

export type FreshnessState = "fresh" | "pending" | "stale" | "missing";

export interface Freshness {
  state: FreshnessState;
  /** yyyy-mm-dd of the snapshot's data date (KST), or null when missing. */
  snapshot_date: string | null;
  /** ISO UTC timestamp the snapshot was generated, or null when missing. */
  generated_at: string | null;
  /** The newest snapshot date that should exist right now (KST weekday). */
  expected_date: string;
  /** ISO UTC timestamp this freshness assessment was computed. */
  checked_at: string;
  /** Human-readable one-liner explaining the state. */
  note: string;
}

const DAY_MS = 86_400_000;
const KST_OFFSET_MS = 9 * 3_600_000;

/**
 * Builds are scheduled at 16:30 KST. Until 17:00 KST we treat "yesterday's
 * snapshot on a weekday afternoon" as pending (the build may be mid-flight or
 * a few minutes late) rather than stale. After 17:00 a missing same-day
 * snapshot is a real failure signal.
 */
const BUILD_START_MIN = 16 * 60 + 30; // 16:30 KST
const BUILD_GRACE_MIN = 17 * 60; //      17:00 KST

/** Date parts in KST for an epoch-ms instant. */
function kstParts(nowMs: number): { date: string; weekday: number; minutes: number } {
  const kst = new Date(nowMs + KST_OFFSET_MS);
  return {
    date: kst.toISOString().slice(0, 10),
    weekday: kst.getUTCDay(), // 0=Sun .. 6=Sat
    minutes: kst.getUTCHours() * 60 + kst.getUTCMinutes(),
  };
}

function shiftDate(isoDate: string, days: number): string {
  const t = Date.parse(`${isoDate}T00:00:00Z`);
  return new Date(t + days * DAY_MS).toISOString().slice(0, 10);
}

function weekdayOf(isoDate: string): number {
  return new Date(Date.parse(`${isoDate}T00:00:00Z`)).getUTCDay();
}

/** Most recent weekday on or before the given KST date. */
function lastWeekdayOnOrBefore(isoDate: string): string {
  let d = isoDate;
  while (weekdayOf(d) === 0 || weekdayOf(d) === 6) d = shiftDate(d, -1);
  return d;
}

/**
 * The newest snapshot date whose scheduled build has completed by `nowMs`.
 *   - Weekday after 17:00 KST → today.
 *   - Weekday before 17:00 KST → previous weekday.
 *   - Saturday / Sunday → the preceding Friday.
 */
export function expectedSnapshotDate(nowMs: number): string {
  const { date, weekday, minutes } = kstParts(nowMs);
  const isWeekday = weekday >= 1 && weekday <= 5;
  if (isWeekday && minutes >= BUILD_GRACE_MIN) return date;
  return lastWeekdayOnOrBefore(shiftDate(date, -1));
}

export function computeFreshness(
  snapshotDate: string | null,
  generatedAt: string | null,
  nowMs: number,
): Freshness {
  const expected = expectedSnapshotDate(nowMs);
  const checkedAt = new Date(nowMs).toISOString();
  const base = {
    snapshot_date: snapshotDate,
    generated_at: generatedAt,
    expected_date: expected,
    checked_at: checkedAt,
  };

  if (!snapshotDate) {
    return {
      ...base,
      state: "missing",
      note: "No snapshot exists yet.",
    };
  }

  // Weekday build window (16:30–17:00 KST) with the previous weekday's
  // snapshot still serving: today's build is due but not late yet.
  const { date: todayKst, weekday, minutes } = kstParts(nowMs);
  const isWeekday = weekday >= 1 && weekday <= 5;
  if (
    isWeekday &&
    minutes >= BUILD_START_MIN &&
    minutes < BUILD_GRACE_MIN &&
    snapshotDate === expected &&
    snapshotDate < todayKst
  ) {
    return {
      ...base,
      state: "pending",
      note: `Today's build (${todayKst}) is in its scheduled window; showing ${snapshotDate}.`,
    };
  }

  if (snapshotDate >= expected) {
    return {
      ...base,
      state: "fresh",
      note: `Snapshot covers ${snapshotDate}, the most recent scheduled build.`,
    };
  }

  return {
    ...base,
    state: "stale",
    note:
      `Snapshot is dated ${snapshotDate} but a build for ${expected} was expected. ` +
      "The data below is the last successful build, not current.",
  };
}
