-- Fresh-install schema; versioned migrations in sql/migrations/ are preferred.
-- Dense minute-level matrices stay in Parquet, not PostgreSQL.
CREATE TABLE raw_alert_events (
    event_id BIGSERIAL PRIMARY KEY,
    region_id TEXT NOT NULL,
    region_name TEXT NOT NULL,
    alert_start TIMESTAMPTZ NOT NULL,
    alert_end TIMESTAMPTZ,
    source TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_id, alert_start, source)
);

CREATE TABLE cleaned_intervals (
    id BIGSERIAL PRIMARY KEY,
    oblast TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    duration_min DOUBLE PRECISION NOT NULL,
    source TEXT,
    interval_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE experiment_runs (
    run_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    git_commit TEXT,
    config_hash TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    model_name TEXT NOT NULL,
    forecast_horizon_minutes INT NOT NULL,
    train_end TIMESTAMPTZ NOT NULL,
    validation_end TIMESTAMPTZ NOT NULL,
    test_end TIMESTAMPTZ NOT NULL,
    pr_auc DOUBLE PRECISION,
    roc_auc DOUBLE PRECISION,
    brier_score DOUBLE PRECISION,
    metrics_json JSONB NOT NULL
);

CREATE TABLE data_quality_checks (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES experiment_runs(run_id) ON DELETE SET NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ix_data_quality_checks_run_id ON data_quality_checks(run_id);
