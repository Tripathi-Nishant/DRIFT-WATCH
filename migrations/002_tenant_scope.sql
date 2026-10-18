-- Add tenant ownership to monitoring history for installations created before
-- organization-aware read endpoints were introduced.
ALTER TABLE models ADD COLUMN IF NOT EXISTS organization_id TEXT;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS organization_id TEXT;
CREATE INDEX IF NOT EXISTS idx_models_org_created ON models(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_org_created ON runs(organization_id, created_at DESC);
