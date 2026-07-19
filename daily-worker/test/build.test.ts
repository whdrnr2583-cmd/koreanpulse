/**
 * Regression tests for the 2026-07 incident class: a DART outage must never
 * overwrite the last known good snapshot, and serve-time freshness must be
 * honest about what is actually stored.
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
import { buildDaily, withFreshnessBanner, withFreshnessField, type Env } from "../src/index";
import { computeFreshness } from "../src/freshness";

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

const FILING = {
  corp_code: "00126380",
  corp_name_ko: "삼성전자",
  stock_code: "005930",
  filing_type: "B",
  title: "주요사항보고서",
  receipt_no: "20260701000001",
  filed_at: "2026-07-01",
  filer_name_ko: null,
  dart_url: "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260701000001",
  attribution: "Source: DART",
};

beforeEach(() => {
  vi.mocked(fetchClassifiedFilings).mockReset();
  vi.mocked(fetchTopFilings).mockReset();
});

describe("buildDaily last-known-good preservation", () => {
  it("throws and writes nothing when every DART stream fails", async () => {
    const { kv, store } = makeKv();
    store.set("daily:json:latest", JSON.stringify({ date: "2026-07-16" }));
    store.set("daily:html:latest", "<html>good</html>");
    vi.mocked(fetchClassifiedFilings).mockRejectedValue(new Error("DART HTTP 503"));
    vi.mocked(fetchTopFilings).mockRejectedValue(new Error("DART HTTP 503"));

    await expect(buildDaily(makeEnv(kv))).rejects.toThrow(/DART unavailable/);
    expect(store.get("daily:json:latest")).toBe(JSON.stringify({ date: "2026-07-16" }));
    expect(store.get("daily:html:latest")).toBe("<html>good</html>");
  });

  it("ships a labelled partial snapshot when only one stream fails", async () => {
    const { kv, store } = makeKv();
    vi.mocked(fetchClassifiedFilings).mockRejectedValue(new Error("DART HTTP 503"));
    vi.mocked(fetchTopFilings).mockResolvedValue([FILING]);

    const result = await buildDaily(makeEnv(kv));
    expect(result.degraded).toEqual(["activist and foreign-holder filings"]);
    const stored = JSON.parse(store.get("daily:json:latest")!);
    expect(stored.degraded).toEqual(["activist and foreign-holder filings"]);
    expect(stored.top_filings).toHaveLength(1);
  });

  it("writes a clean snapshot when both streams succeed", async () => {
    const { kv, store } = makeKv();
    vi.mocked(fetchClassifiedFilings).mockResolvedValue({ activists: [], foreign_flows: [] });
    vi.mocked(fetchTopFilings).mockResolvedValue([FILING]);

    const result = await buildDaily(makeEnv(kv));
    expect(result.degraded).toEqual([]);
    const stored = JSON.parse(store.get("daily:json:latest")!);
    expect(stored.degraded).toBeUndefined();
    expect(stored.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(stored.generated_at).toBeTruthy();
  });

  it("surfaces a KV write failure instead of reporting success", async () => {
    const { kv } = makeKv();
    (kv.put as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("KV quota exceeded"));
    vi.mocked(fetchClassifiedFilings).mockResolvedValue({ activists: [], foreign_flows: [] });
    vi.mocked(fetchTopFilings).mockResolvedValue([FILING]);

    await expect(buildDaily(makeEnv(kv))).rejects.toThrow(/KV quota/);
  });
});

describe("serve-time freshness", () => {
  const SUNDAY_NOON_KST = Date.parse("2026-07-19T12:00:00Z") - 9 * 3_600_000;

  it("withFreshnessField attaches a freshness object to the stored snapshot", () => {
    const stored = JSON.stringify({ date: "2026-07-16", generated_at: "2026-07-16T07:31:00Z" });
    const out = JSON.parse(withFreshnessField(stored, SUNDAY_NOON_KST));
    expect(out.freshness.state).toBe("stale"); // Thursday data on Sunday
    expect(out.freshness.snapshot_date).toBe("2026-07-16");
    expect(out.freshness.expected_date).toBe("2026-07-17");
  });

  it("withFreshnessField passes through unparseable stored bytes unchanged", () => {
    expect(withFreshnessField("not json", SUNDAY_NOON_KST)).toBe("not json");
  });

  it("withFreshnessBanner injects a stale banner after <body>", () => {
    const freshness = computeFreshness("2026-07-16", "2026-07-16T07:31:00Z", SUNDAY_NOON_KST);
    const out = withFreshnessBanner('<html><body class="x"><p>hi</p></body></html>', freshness);
    expect(out).toContain("This snapshot is stale.");
    expect(out.indexOf("stale")).toBeLessThan(out.indexOf("<p>hi</p>"));
  });

  it("withFreshnessBanner leaves fresh pages untouched", () => {
    const freshness = computeFreshness("2026-07-17", "2026-07-17T07:31:00Z", SUNDAY_NOON_KST);
    const html = "<html><body><p>hi</p></body></html>";
    expect(withFreshnessBanner(html, freshness)).toBe(html);
  });
});
