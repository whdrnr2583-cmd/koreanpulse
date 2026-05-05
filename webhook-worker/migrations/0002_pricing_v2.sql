-- 0002_pricing_v2.sql — pricing v2 plan-name expansion (2026-05-05).
-- Adds 'solo' / 'analyst' / 'desk' to the licenses.plan CHECK constraint
-- alongside the deprecated 'free' / 'starter' / 'indie' / 'pro' /
-- 'enterprise' values (kept for back-compat with historical rows).
--
-- SQLite has no ALTER TABLE … MODIFY CONSTRAINT, so we recreate the table.
-- Cloudflare D1 rejects explicit `BEGIN TRANSACTION` / `COMMIT`; wrangler
-- runs the file as a single atomic batch automatically.
--
-- Apply with:
--   npx wrangler d1 execute koreanpulse_db --file ./migrations/0002_pricing_v2.sql

-- 1. New table with the expanded CHECK constraint.
CREATE TABLE IF NOT EXISTS licenses_v2 (
    key                 TEXT PRIMARY KEY,
    plan                TEXT NOT NULL CHECK (plan IN (
        -- Active (pricing v2)
        'solo','analyst','desk',
        -- Deprecated aliases — historical rows. Kept so old data resolves.
        'free','starter','indie','pro','enterprise'
    )),
    customer_email      TEXT NOT NULL,
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    period_calls        INTEGER NOT NULL DEFAULT 0,
    period_started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    metadata            TEXT NOT NULL DEFAULT '{}',
    is_lifetime         INTEGER NOT NULL DEFAULT 0,
    deal_seq            INTEGER,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2. Move data over (zero rows in v0, but the migration must be safe
-- for any environment where rows already exist).
INSERT OR IGNORE INTO licenses_v2 SELECT * FROM licenses;

-- 3. Swap the tables.
DROP TABLE licenses;
ALTER TABLE licenses_v2 RENAME TO licenses;

-- 4. Recreate the indexes (the swap drops them).
CREATE INDEX IF NOT EXISTS licenses_email_lower_idx
    ON licenses (LOWER(customer_email));

CREATE INDEX IF NOT EXISTS licenses_active_idx
    ON licenses (active) WHERE active = 1;

CREATE INDEX IF NOT EXISTS licenses_lifetime_idx
    ON licenses (is_lifetime, deal_seq) WHERE is_lifetime = 1;

-- 5. Recreate the updated_at trigger.
DROP TRIGGER IF EXISTS licenses_updated_at_trg;
CREATE TRIGGER licenses_updated_at_trg
    AFTER UPDATE ON licenses
    FOR EACH ROW
    BEGIN
        UPDATE licenses SET updated_at = datetime('now') WHERE key = OLD.key;
    END;
