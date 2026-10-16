/**
 * The snapshot date is the latest business day whose 16:30 KST publish time
 * has passed — not the wall-clock date. A late backstop run (after midnight
 * KST) must rebuild the prior business day instead of overwriting latest with
 * a snapshot labelled with the next KST date (whose 16:30 publish time has
 * not passed) while carrying the previous business day's filings.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/dart", () => ({
  fetchClassifiedFilings: vi.fn(),
  fetchTopFilings: vi.fn(),
}));
vi.mock("../src/translate", () => ({
  generateTakeaway: vi.fn(async () => ["bullet"]),
  summariseFiling: vi.fn(async () => "summary"),
  translateCorpName: vi.fn(async () => "Samsung Electronics"),
  translateTitle: vi.fn(async () => "Translated title"),
}));
vi.mock("../src/discord", () => ({
  postToDiscord: vi.fn(async () => ({ ok: true })),
}));

import { fetchClassifiedFilings, fetchTopFilings } from "../src/dart";
import worker, { buildDaily, type Env } from "../src/index";
import { buildSnapshotDate } from "../src/freshness";

// 2026-10-02 Friday, 10-03 Saturday, 10-04 Sunday, 10-05 Monday, 10-06 Tuesday.
// KST = UTC+9, so a KST wall-clock time is the same string minus 9 hours.
const kst = (isoLocal: string) => Date.parse(`${isoLocal}Z`) - 9 * 3_600_000;

function makeKv() {
  const store = new Map<string, string>();
  return {
    store,
    kv: {
      get: vi.fn(async (k: string) => store.get(k) ?? null),
      put: vi.fn(async (k: string, v: string) => {
        store.set(k, v);
      }),
    } as unknown as KVNamespace,
  };
}

function makeEnv(kv: KVNamespace): Env {
  return {
    DAILY: kv,
    DART_API_KEY: "test-key",
    DART_API_BASE: "https://example.invalid",
    OPENAI_API_KEY: "test-key",
    LLM_MODEL: "test-model",
    SITE_URL: "https://koreanpulse.dev",
    HISTORY_DAYS: "30",
  };
}

beforeEach(() => {
  vi.mocked(fetchClassifiedFilings).mockReset();
  vi.mocked(fetchTopFilings).mockReset();
  vi.mocked(fetchClassifiedFilings).mockResolvedValue({ activists: [], foreign_flows: [] });
  vi.mocked(fetchTopFilings).mockResolvedValue([]);
});

describe("buildSnapshotDate", () => {
  it("Tuesday 02:00 KST (late backstop) -> Monday", () => {
    expect(buildSnapshotDate(kst("2026-10-06T02:00:00"))).toBe("2026-10-05");
  });

  it("Tuesday 16:31 KST -> Tuesday", () => {
    expect(buildSnapshotDate(kst("2026-10-06T16:31:00"))).toBe("2026-10-06");
  });

  it("Saturday 10:00 KST -> Friday", () => {
    expect(buildSnapshotDate(kst("2026-10-03T10:00:00"))).toBe("2026-10-02");
  });

  it("Monday 09:00 KST -> previous Friday", () => {
    expect(buildSnapshotDate(kst("2026-10-05T09:00:00"))).toBe("2026-10-02");
  });

  it("regular cron instant (16:30:00 KST = 07:30:00 UTC) -> same day", () => {
    expect(buildSnapshotDate(Date.parse("2026-10-06T07:30:00Z"))).toBe("2026-10-06");
    expect(buildSnapshotDate(Date.parse("2026-10-05T07:30:00Z"))).toBe("2026-10-05");
  });

  it("one minute before publish time still yields the previous business day", () => {
    expect(buildSnapshotDate(kst("2026-10-06T16:29:00"))).toBe("2026-10-05");
  });

  it("weekday 16:29:59 KST -> previous business day", () => {
    expect(buildSnapshotDate(kst("2026-10-06T16:29:59"))).toBe("2026-10-05");
  });

  it("weekday 16:30:30 KST -> same day", () => {
    expect(buildSnapshotDate(kst("2026-10-06T16:30:30"))).toBe("2026-10-06");
  });

  it("regular cron firing a few seconds late (07:30:23Z) -> same day", () => {
    expect(buildSnapshotDate(Date.parse("2026-10-06T07:30:23Z"))).toBe("2026-10-06");
  });

  it("Sunday -> preceding Friday", () => {
    expect(buildSnapshotDate(kst("2026-10-04T12:00:00"))).toBe("2026-10-02");
  });

  it("Friday 23:50 KST -> Friday", () => {
    expect(buildSnapshotDate(kst("2026-10-02T23:50:00"))).toBe("2026-10-02");
  });

  it("Tuesday 00:10 KST -> Monday", () => {
    expect(buildSnapshotDate(kst("2026-10-06T00:10:00"))).toBe("2026-10-05");
  });
});

describe("buildDaily snapshot date", () => {
  it("late run after midnight KST builds the prior business day and keys it by that date", async () => {
    const { kv, store } = makeKv();
    const result = await buildDaily(makeEnv(kv), kst("2026-10-06T02:00:00"));
    expect(result.date).toBe("2026-10-05");
    expect(JSON.parse(store.get("daily:json:latest")!).date).toBe("2026-10-05");
    expect(store.has("daily:json:2026-10-05")).toBe(true);
    expect(store.has("daily:json:2026-10-06")).toBe(false);
  });

  it("pins both DART query windows to the snapshot date", async () => {
    const { kv } = makeKv();
    await buildDaily(makeEnv(kv), kst("2026-10-06T02:00:00"));
    expect(fetchClassifiedFilings).toHaveBeenCalledWith(expect.anything(), 7, "2026-10-05");
    expect(fetchTopFilings).toHaveBeenCalledWith(expect.anything(), 1, 10, "2026-10-05");
  });

  it("regular cron time builds today", async () => {
    const { kv, store } = makeKv();
    const result = await buildDaily(makeEnv(kv), Date.parse("2026-10-06T07:30:00Z"));
    expect(result.date).toBe("2026-10-06");
    expect(JSON.parse(store.get("daily:json:latest")!).date).toBe("2026-10-06");
    expect(fetchClassifiedFilings).toHaveBeenCalledWith(expect.anything(), 7, "2026-10-06");
  });

  it("Saturday run rebuilds Friday", async () => {
    const { kv } = makeKv();
    const result = await buildDaily(makeEnv(kv), kst("2026-10-03T10:00:00"));
    expect(result.date).toBe("2026-10-02");
  });

  it("rebuilding the same business day twice overwrites the same keys", async () => {
    const { kv, store } = makeKv();
    await buildDaily(makeEnv(kv), kst("2026-10-06T02:00:00"));
    const keysAfterFirst = [...store.keys()].sort();
    await buildDaily(makeEnv(kv), kst("2026-10-06T03:00:00"));
    expect([...store.keys()].sort()).toEqual(keysAfterFirst);
    expect(JSON.parse(store.get("daily:json:latest")!).date).toBe("2026-10-05");
  });
});

describe("scheduled handler clock floor", () => {
  it("clock read 5 ms before the scheduled instant still builds that day", async () => {
    const { kv, store } = makeKv();
    vi.useFakeTimers();
    try {
      vi.setSystemTime(Date.parse("2026-10-06T07:29:59.995Z"));
      const pending: Promise<unknown>[] = [];
      const ctx = { waitUntil: (p: Promise<unknown>) => void pending.push(p) } as unknown as ExecutionContext;
      const event = {
        cron: "30 7 * * MON-FRI",
        scheduledTime: Date.parse("2026-10-06T07:30:00.000Z"),
        noRetry() {},
      } as unknown as ScheduledController;
      await worker.scheduled(event, makeEnv(kv), ctx);
      await Promise.all(pending);
    } finally {
      vi.useRealTimers();
    }
    expect(JSON.parse(store.get("daily:json:latest")!).date).toBe("2026-10-06");
    expect(fetchClassifiedFilings).toHaveBeenCalledWith(expect.anything(), 7, "2026-10-06");
  });
});
