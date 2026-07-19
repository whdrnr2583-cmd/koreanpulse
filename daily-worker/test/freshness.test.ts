import { describe, expect, it } from "vitest";
import { computeFreshness, expectedSnapshotDate } from "../src/freshness";

// 2026-07-17 is a Friday, 2026-07-18 Saturday, 2026-07-19 Sunday,
// 2026-07-20 Monday. KST = UTC+9.
const kst = (iso: string) => Date.parse(iso) - 9 * 3_600_000;

describe("expectedSnapshotDate", () => {
  it("weekday after 17:00 KST expects same-day snapshot", () => {
    expect(expectedSnapshotDate(kst("2026-07-17T17:00:00Z"))).toBe("2026-07-17");
    expect(expectedSnapshotDate(kst("2026-07-17T23:59:00Z"))).toBe("2026-07-17");
  });

  it("weekday before the build window expects the previous weekday", () => {
    expect(expectedSnapshotDate(kst("2026-07-17T09:00:00Z"))).toBe("2026-07-16");
    // Monday morning reaches back across the weekend to Friday.
    expect(expectedSnapshotDate(kst("2026-07-20T09:00:00Z"))).toBe("2026-07-17");
  });

  it("weekday inside the 16:30–17:00 window still expects the previous weekday", () => {
    expect(expectedSnapshotDate(kst("2026-07-17T16:45:00Z"))).toBe("2026-07-16");
  });

  it("Saturday and Sunday expect the preceding Friday", () => {
    expect(expectedSnapshotDate(kst("2026-07-18T12:00:00Z"))).toBe("2026-07-17");
    expect(expectedSnapshotDate(kst("2026-07-19T12:00:00Z"))).toBe("2026-07-17");
  });
});

describe("computeFreshness", () => {
  it("missing snapshot", () => {
    const f = computeFreshness(null, null, kst("2026-07-18T12:00:00Z"));
    expect(f.state).toBe("missing");
    expect(f.snapshot_date).toBeNull();
  });

  it("fresh on the weekend when the Friday snapshot exists", () => {
    const f = computeFreshness("2026-07-17", "2026-07-17T07:31:00.000Z", kst("2026-07-19T12:00:00Z"));
    expect(f.state).toBe("fresh");
  });

  it("fresh on a weekday morning with yesterday's snapshot", () => {
    const f = computeFreshness("2026-07-16", "2026-07-16T07:31:00.000Z", kst("2026-07-17T09:00:00Z"));
    expect(f.state).toBe("fresh");
  });

  it("pending inside the build window with the previous weekday's snapshot", () => {
    const f = computeFreshness("2026-07-16", "2026-07-16T07:31:00.000Z", kst("2026-07-17T16:45:00Z"));
    expect(f.state).toBe("pending");
  });

  it("stale after 17:00 KST when today's weekday build did not land", () => {
    const f = computeFreshness("2026-07-16", "2026-07-16T07:31:00.000Z", kst("2026-07-17T17:30:00Z"));
    expect(f.state).toBe("stale");
    expect(f.expected_date).toBe("2026-07-17");
    expect(f.note).toContain("expected");
  });

  it("stale on the weekend when even Friday's build is missing (the 2026-07-19 incident shape)", () => {
    // Live incident: Thursday's snapshot still serving on Saturday.
    const f = computeFreshness("2026-07-17", "2026-07-17T10:03:00.000Z", kst("2026-07-19T12:00:00Z"));
    expect(f.state).toBe("fresh"); // 7/17 IS the preceding Friday — fresh…
    const g = computeFreshness("2026-07-16", "2026-07-16T10:03:00.000Z", kst("2026-07-19T12:00:00Z"));
    expect(g.state).toBe("stale"); // …but a Thursday date on Sunday is stale.
  });

  it("a snapshot dated in the future of the expectation is fresh (manual weekend rebuild)", () => {
    const f = computeFreshness("2026-07-19", "2026-07-19T03:00:00.000Z", kst("2026-07-19T12:00:00Z"));
    expect(f.state).toBe("fresh");
  });
});
