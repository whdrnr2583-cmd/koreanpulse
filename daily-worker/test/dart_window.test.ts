/** DART query windows follow the snapshot date passed in, not the wall clock. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchClassifiedFilings, fetchTopFilings } from "../src/dart";
import type { Env } from "../src/index";

const env = {
  DART_API_KEY: "test-key",
  DART_API_BASE: "https://example.invalid",
} as unknown as Env;

function stubFetch() {
  const fn = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ status: "013", message: "no data" }),
  }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

function windowOf(call: unknown[]): { bgn: string | null; end: string | null } {
  const params = new URL(call[0] as string).searchParams;
  return { bgn: params.get("bgn_de"), end: params.get("end_de") };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DART window with asOf", () => {
  it("classified filings: 7-day window ends on the snapshot date", async () => {
    const fn = stubFetch();
    await fetchClassifiedFilings(env, 7, "2026-10-05");
    expect(windowOf(fn.mock.calls[0])).toEqual({ bgn: "20260928", end: "20261005" });
  });

  it("top filings: 1-day window ends on the snapshot date for both streams", async () => {
    const fn = stubFetch();
    await fetchTopFilings(env, 1, 10, "2026-10-05");
    expect(fn.mock.calls).toHaveLength(2);
    for (const call of fn.mock.calls) {
      expect(windowOf(call)).toEqual({ bgn: "20261004", end: "20261005" });
    }
  });

  it("without asOf the window still ends on the current date", async () => {
    const fn = stubFetch();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-06T07:30:00Z"));
    try {
      await fetchTopFilings(env, 1, 10);
    } finally {
      vi.useRealTimers();
    }
    expect(windowOf(fn.mock.calls[0])).toEqual({ bgn: "20261005", end: "20261006" });
  });
});
