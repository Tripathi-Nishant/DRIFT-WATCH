-- PostgreSQL baseline schema. Apply with a migration runner in deployment order.
CREATE TABLE IF NOT EXISTS organizations (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memberships (user_id TEXT NOT NULL, organization_id TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY(user_id, organization_id));
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, model_type TEXT NOT NULL, created_at TEXT NOT NULL, reference_profile JSONB);
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, model_id TEXT, severity TEXT NOT NULL, decision TEXT NOT NULL, created_at TEXT NOT NULL, report JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS predictions (id TEXT PRIMARY KEY, model_id TEXT, prediction TEXT NOT NULL, features JSONB NOT NULL, created_at TEXT NOT NULL, label TEXT);
CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, prediction_id TEXT NOT NULL, label TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, detail TEXT);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, organization_id TEXT, user_id TEXT, action TEXT NOT NULL, entity_type TEXT, entity_id TEXT, detail TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retraining_requests (id TEXT PRIMARY KEY, organization_id TEXT, model_id TEXT, status TEXT NOT NULL, requested_by TEXT, approved_by TEXT, report JSONB NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_model_id ON runs(model_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model_created ON predictions(model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_org_created ON audit_events(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_run ON alerts(run_id);
