-- 0001_licenses.sql — initial D1 schema for Cloudflare-hosted license store.
-- D1 is SQLite under the hood; some Postgres features don't translate:
--   - JSONB → TEXT (we store JSON-serialized metadata)
--   - TIMESTAMPTZ → TEXT (ISO 8601 strings)
--   - JSONB functional indexes → simple secondary indexes on derived columns
--
-- Apply with:
--   npx wrangler d1 execute koreanpulse_db --file ./migrations/0001_licenses.sql
--
-- Idempotent: re-running is safe.

CREATE TABLE IF NOT EXISTS licenses (
    key                 TEXT PRIMARY KEY,
    plan                TEXT NOT NULL CHECK (plan IN ('free','starter','indie','pro','enterprise')),
    customer_email      TEXT NOT NULL,
    active              INTEGER NOT NULL DEFAULT 1,    -- 0/1 for SQLite
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    period_calls        INTEGER NOT NULL DEFAULT 0,
    period_started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    metadata            TEXT NOT NULL DEFAULT '{}',     -- JSON-serialized
    -- Denormalized columns for index-friendly queries (D1 has no JSONB indexes):
    is_lifetime         INTEGER NOT NULL DEFAULT 0,    -- 0/1, mirrored from metadata.lifetime
    deal_seq            INTEGER,                        -- mirrored from metadata.deal_seq
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Email lookup is the hottest query (webhook handler resolves customer_email
-- → existing license on every event). LOWER() to keep it case-insensitive.
CREATE INDEX IF NOT EXISTS licenses_email_lower_idx
    ON licenses (LOWER(customer_email));

-- Active licenses get touched constantly (per-call usage increment).
CREATE INDEX IF NOT EXISTS licenses_active_idx
    ON licenses (active) WHERE active = 1;

-- Lifetime deal accounting: COUNT and MAX(deal_seq) used by order_created handler.
CREATE INDEX IF NOT EXISTS licenses_lifetime_idx
    ON licenses (is_lifetime, deal_seq) WHERE is_lifetime = 1;

-- Trigger to bump updated_at on every change (D1 supports SQLite triggers).
DROP TRIGGER IF EXISTS licenses_updated_at_trg;
CREATE TRIGGER licenses_updated_at_trg
    AFTER UPDATE ON licenses
    FOR EACH ROW
    BEGIN
        UPDATE licenses SET updated_at = datetime('now') WHERE key = OLD.key;
    END;

-- Idempotency log for Lemon Squeezy webhook events. Replaces the in-memory
-- `_seen` LRU in the Python lemonsqueezy module — D1 row is the source of
-- truth and survives Worker cold starts.
CREATE TABLE IF NOT EXISTS webhook_events (
    webhook_id          TEXT PRIMARY KEY,
    event_name          TEXT NOT NULL,
    received_at         TEXT NOT NULL DEFAULT (datetime('now')),
    license_key         TEXT,                            -- if action issued/upgraded
    action              TEXT,                            -- "issued" | "upgraded" | …
    note                TEXT
);

CREATE INDEX IF NOT EXISTS webhook_events_received_idx
    ON webhook_events (received_at);
