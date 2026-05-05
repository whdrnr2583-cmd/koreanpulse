-- 001_licenses.sql — initial schema for Postgres-backed LicenseStore.
-- Apply against any Postgres 14+ (Supabase, RDS, self-hosted).
--
-- Idempotent: rerunning is safe (CREATE TABLE IF NOT EXISTS, etc.).

CREATE TABLE IF NOT EXISTS licenses (
    id                  BIGSERIAL PRIMARY KEY,
    key                 TEXT NOT NULL UNIQUE,
    plan                TEXT NOT NULL,
    customer_email      TEXT NOT NULL,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_calls        INTEGER NOT NULL DEFAULT 0,
    period_started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Plan must be one of the values defined in koreanpulse.license.Plan.
ALTER TABLE licenses
    DROP CONSTRAINT IF EXISTS licenses_plan_check;
ALTER TABLE licenses
    ADD  CONSTRAINT licenses_plan_check
    CHECK (plan IN ('free', 'starter', 'indie', 'pro', 'enterprise'));

-- Email lookup is the hottest query (webhook handler resolves customer_email
-- → existing license on every event). Lower() so case-insensitive.
CREATE INDEX IF NOT EXISTS licenses_email_lower_idx
    ON licenses (LOWER(customer_email));

-- Active licenses get touched constantly (per-call increment_usage); covering
-- index speeds up WHERE active = TRUE filters.
CREATE INDEX IF NOT EXISTS licenses_active_idx
    ON licenses (active) WHERE active = TRUE;

-- Lifetime deal accounting: count + max(deal_seq) used by webhook handler.
-- Functional index on the JSONB tag keeps that scan tiny.
CREATE INDEX IF NOT EXISTS licenses_lifetime_idx
    ON licenses ((metadata->>'lifetime'))
    WHERE metadata->>'lifetime' = 'true';

-- updated_at trigger so we can debug "when did this license last change".
CREATE OR REPLACE FUNCTION licenses_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS licenses_updated_at_trg ON licenses;
CREATE TRIGGER licenses_updated_at_trg
    BEFORE UPDATE ON licenses
    FOR EACH ROW
    EXECUTE FUNCTION licenses_set_updated_at();
