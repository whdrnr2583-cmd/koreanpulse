import { describe, expect, it, vi } from "vitest";
import {
  handleSignup,
  normalizeEmail,
  normalizeRole,
  type SignupEnv,
} from "../src/signup";

const SECRET = "test-secret-value";

/** Minimal D1 mock: in-memory row map keyed by email. */
function makeDb(opts: { failWrites?: boolean } = {}) {
  const rows = new Map<string, Record<string, unknown>>();
  const prepare = (sql: string) => ({
    bind: (...args: unknown[]) => ({
      first: async () => {
        if (opts.failWrites && !sql.startsWith("SELECT")) throw new Error("D1 down");
        if (sql.startsWith("SELECT")) {
          const row = rows.get(args[0] as string);
          return row ? { id: 1 } : null;
        }
        return null;
      },
      run: async () => {
        if (opts.failWrites) throw new Error("D1 down");
        if (sql.startsWith("INSERT")) {
          rows.set(args[0] as string, { role: args[1], source: args[2] });
        } else if (sql.startsWith("UPDATE")) {
          const row = rows.get(args[2] as string);
          if (row) row.role = args[0];
        }
        return { success: true };
      },
    }),
  });
  return { rows, db: { prepare } as unknown as D1Database };
}

function makeEnv(db: D1Database, secret: string | null = SECRET): SignupEnv {
  return { DB: db, SIGNUP_SHARED_SECRET: secret ?? undefined };
}

function req(body: unknown, key: string | null = SECRET): Request {
  return new Request("https://api.koreanpulse.dev/v1/signup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key === null ? {} : { "x-signup-key": key }),
    },
    body: JSON.stringify(body),
  });
}

const VALID = {
  email: "Person@Example.com ",
  role: "analyst",
  consent: true,
  consent_version: "2026-05-27",
  source: "koreanpulse.dev/landing",
};

describe("normalizeEmail", () => {
  it("trims and lower-cases", () => {
    expect(normalizeEmail("  A.B@Example.COM ")).toBe("a.b@example.com");
  });
  it("rejects junk", () => {
    for (const bad of ["", "a", "a@b", "a b@c.com", "@x.com", "a@", `${"x".repeat(255)}@a.io`, 42, null]) {
      expect(normalizeEmail(bad as never)).toBeNull();
    }
  });
});

describe("normalizeRole", () => {
  it("accepts known roles, empty → unknown, rejects others", () => {
    expect(normalizeRole("analyst")).toBe("analyst");
    expect(normalizeRole("")).toBe("unknown");
    expect(normalizeRole(undefined)).toBe("unknown");
    expect(normalizeRole("hacker")).toBeNull();
  });
});

describe("handleSignup", () => {
  it("stores a valid signup and returns ok", async () => {
    const { rows, db } = makeDb();
    const res = await handleSignup(req(VALID), makeEnv(db));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, duplicate: false });
    expect(rows.has("person@example.com")).toBe(true);
  });

  it("rejects an invalid email with 400", async () => {
    const { db } = makeDb();
    const res = await handleSignup(req({ ...VALID, email: "not-an-email" }), makeEnv(db));
    expect(res.status).toBe(400);
  });

  it("rejects an unknown role with 400", async () => {
    const { db } = makeDb();
    const res = await handleSignup(req({ ...VALID, role: "wizard" }), makeEnv(db));
    expect(res.status).toBe(400);
  });

  it("rejects missing consent with 400", async () => {
    const { db } = makeDb();
    const res = await handleSignup(req({ ...VALID, consent: false }), makeEnv(db));
    expect(res.status).toBe(400);
  });

  it("treats a duplicate signup as idempotent success", async () => {
    const { db } = makeDb();
    const env = makeEnv(db);
    await handleSignup(req(VALID), env);
    const res = await handleSignup(req({ ...VALID, role: "developer" }), env);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, duplicate: true });
  });

  it("returns 500 when persistence fails (never a fake success)", async () => {
    const { db } = makeDb({ failWrites: true });
    const res = await handleSignup(req(VALID), makeEnv(db));
    expect(res.status).toBe(500);
    expect(((await res.json()) as { ok: boolean }).ok).toBe(false);
  });

  it("rejects a missing or wrong shared secret with 403", async () => {
    const { db } = makeDb();
    expect((await handleSignup(req(VALID, null), makeEnv(db))).status).toBe(403);
    expect((await handleSignup(req(VALID, "wrong"), makeEnv(db))).status).toBe(403);
  });

  it("returns 500 when the server has no secret configured", async () => {
    const { db } = makeDb();
    const res = await handleSignup(req(VALID), makeEnv(db, null));
    expect(res.status).toBe(500);
  });

  it("never logs the raw email address", async () => {
    const spy = vi.spyOn(console, "log").mockImplementation(() => {});
    const { db } = makeDb();
    await handleSignup(req(VALID), makeEnv(db));
    const logged = spy.mock.calls.flat().join(" ");
    expect(logged).not.toContain("person@example.com");
    spy.mockRestore();
  });
});
