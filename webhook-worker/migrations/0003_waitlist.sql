-- 0003_waitlist.sql — durable storage for landing-page email signups.
--
-- Before this table the "waitlist" existed only as Vercel function logs plus
-- a fire-and-forget Discord webhook: a webhook outage silently lost signups
-- while the UI showed success. D1 is the durable source of truth; the Discord
-- ping is a secondary notification.
--
-- Apply with:
--   npx wrangler d1 execute koreanpulse_db --remote --file ./migrations/0003_waitlist.sql

CREATE TABLE IF NOT EXISTS waitlist (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  email           TEXT NOT NULL UNIQUE,      -- normalized (trimmed, lower-cased)
  role            TEXT NOT NULL DEFAULT 'unknown',
  source          TEXT NOT NULL DEFAULT 'unknown',
  consent_at      TEXT,                      -- ISO timestamp the consent box was accepted
  consent_version TEXT,                      -- privacy-policy version shown at consent time
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON waitlist (created_at);
