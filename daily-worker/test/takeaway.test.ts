/**
 * The /today page is English-only. A Korean "Today's takeaway" is retried once
 * with a stronger instruction; if it is still Korean the takeaway is dropped
 * (and not cached) rather than published in Korean.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  generateTakeaway,
  hasKoreanBullet,
  koreanRatio,
  KOREAN_RATIO_THRESHOLD,
} from "../src/translate";
import type { Env } from "../src/index";

const DIGEST = [
  {
    kind: "foreign" as const,
    filer: "BlackRock",
    corp: "셀리드",
    ticker: "299660",
    title_en: "Report on large holdings",
  },
];

const KOREAN_BULLET = "블랙록이 셀리드 지분을 5% 이상 보유한 것으로 보고했다";
const ENGLISH_BULLET =
  "BlackRock reported a stake above 5% in Cellid 셀리드 (299660), per a DART large-holdings filing.";

function makeEnv() {
  const store = new Map<string, string>();
  const kv = {
    get: vi.fn(async (k: string) => store.get(k) ?? null),
    put: vi.fn(async (k: string, v: string) => {
      store.set(k, v);
    }),
  } as unknown as KVNamespace;
  const env = { DAILY: kv, LLM_MODEL: "test-model", OPENAI_API_KEY: "test-key" } as unknown as Env;
  return { env, store, kv };
}

function mockOpenAI(...contents: string[]) {
  const fn = vi.fn();
  for (const c of contents) {
    fn.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ choices: [{ message: { content: c }, finish_reason: "stop" }] }),
    });
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

function systemPromptOf(fn: ReturnType<typeof vi.fn>, call: number): string {
  const body = JSON.parse(fn.mock.calls[call][1].body as string);
  return body.messages[0].content as string;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("koreanRatio", () => {
  it("is 0 for an English bullet and for text without letters", () => {
    expect(koreanRatio("BlackRock raised its stake in Samsung Electronics (005930) to 5.1%.")).toBe(0);
    expect(koreanRatio("123 45% --")).toBe(0);
    expect(koreanRatio("")).toBe(0);
  });

  it("stays under the threshold for an English bullet with a Korean name in parentheses", () => {
    expect(koreanRatio(ENGLISH_BULLET)).toBeLessThan(KOREAN_RATIO_THRESHOLD);
    // Even the bare name pair from a filing line passes.
    expect(koreanRatio("Cellid 셀리드 299660")).toBeLessThan(KOREAN_RATIO_THRESHOLD);
    expect(hasKoreanBullet([ENGLISH_BULLET])).toBe(false);
  });

  it("exceeds the threshold for a fully Korean bullet", () => {
    expect(koreanRatio(KOREAN_BULLET)).toBeGreaterThan(KOREAN_RATIO_THRESHOLD);
    expect(koreanRatio("삼성전자")).toBe(1);
    expect(hasKoreanBullet([ENGLISH_BULLET, KOREAN_BULLET])).toBe(true);
  });
});

describe("hasKoreanBullet known limits (current verdicts pinned, not endorsed)", () => {
  it("misses a Korean sentence with long English proper names (ratio under threshold)", () => {
    // Known limitation: Korean bullet that slips through.
    const a = "BlackRock Fund Advisors가 삼성전자(005930) 지분 5% 이상 보유 보고";
    const b = "Norges Bank Investment Management가 SK하이닉스(000660) 지분 보유 보고";
    expect(koreanRatio(a)).toBeLessThan(KOREAN_RATIO_THRESHOLD);
    expect(koreanRatio(b)).toBeLessThan(KOREAN_RATIO_THRESHOLD);
    expect(hasKoreanBullet([a])).toBe(false);
    expect(hasKoreanBullet([b])).toBe(false);
  });

  it("rejects an English bullet with a long Hangul company name and little other English", () => {
    // Known limitation: English bullet that is flagged as Korean.
    const c = "삼성바이오로직스 (207940) — CB issuance.";
    expect(koreanRatio(c)).toBeGreaterThan(KOREAN_RATIO_THRESHOLD);
    expect(hasKoreanBullet([c])).toBe(true);
  });
});

describe("generateTakeaway language guard", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("English first answer: one call, cached, English instruction present", async () => {
    const { env, store } = makeEnv();
    const fn = mockOpenAI(ENGLISH_BULLET);
    const out = await generateTakeaway(env, "2026-10-05", DIGEST);
    expect(out).toEqual([ENGLISH_BULLET]);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(systemPromptOf(fn, 0)).toContain("Write every bullet in English.");
    expect([...store.keys()].filter((k) => k.startsWith("translate:td:"))).toHaveLength(1);
  });

  it("Korean first answer, English retry: returns the retry and caches it", async () => {
    const { env, store } = makeEnv();
    const fn = mockOpenAI(KOREAN_BULLET, ENGLISH_BULLET);
    const out = await generateTakeaway(env, "2026-10-05", DIGEST);
    expect(out).toEqual([ENGLISH_BULLET]);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(systemPromptOf(fn, 1)).toContain("Respond in English only");
    const cachedKey = [...store.keys()].find((k) => k.startsWith("translate:td:"))!;
    expect(JSON.parse(store.get(cachedKey)!)).toEqual([ENGLISH_BULLET]);
  });

  it("Korean twice: returns [] after exactly two calls and caches nothing", async () => {
    const { env, store, kv } = makeEnv();
    const fn = mockOpenAI(KOREAN_BULLET, KOREAN_BULLET);
    const out = await generateTakeaway(env, "2026-10-05", DIGEST);
    expect(out).toEqual([]);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(kv.put).not.toHaveBeenCalled();
    expect(store.size).toBe(0);
  });

  it("a Korean takeaway cached before the guard existed is regenerated", async () => {
    const { env, store } = makeEnv();
    // Seed the cache entry the same way a previous deploy would have.
    const fn1 = mockOpenAI(ENGLISH_BULLET);
    await generateTakeaway(env, "2026-10-05", DIGEST);
    const key = [...store.keys()].find((k) => k.startsWith("translate:td:"))!;
    store.set(key, JSON.stringify([KOREAN_BULLET]));
    expect(fn1).toHaveBeenCalledTimes(1);

    const fn2 = mockOpenAI(ENGLISH_BULLET);
    const out = await generateTakeaway(env, "2026-10-05", DIGEST);
    expect(out).toEqual([ENGLISH_BULLET]);
    expect(fn2).toHaveBeenCalledTimes(1);
  });

  it("a cached English takeaway is returned without calling the model", async () => {
    const { env } = makeEnv();
    mockOpenAI(ENGLISH_BULLET);
    await generateTakeaway(env, "2026-10-05", DIGEST);
    const fn = mockOpenAI();
    const out = await generateTakeaway(env, "2026-10-05", DIGEST);
    expect(out).toEqual([ENGLISH_BULLET]);
    expect(fn).not.toHaveBeenCalled();
  });
});
