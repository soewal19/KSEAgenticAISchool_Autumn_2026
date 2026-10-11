-- Fresh-install migration. Safe to re-run while tables remain empty/compatible.
BEGIN;

CREATE TABLE IF NOT EXISTS raw_alert_events (
    event_id BIGSERIAL PRIMARY KEY,
    region_id TEXT NOT NULL,
    region_name TEXT NOT NULL,
    alert_start TIMESTAMPTZ NOT NULL,
    alert_end TIMESTAMPTZ,
    source TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_id, alert_start, source)
);

CREATE TABLE IF NOT EXISTS cleaned_intervals (
    id BIGSERIAL PRIMARY KEY,
    oblast TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    duration_min DOUBLE PRECISION NOT NULL,
    source TEXT,
    interval_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_runs (
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

CREATE TABLE IF NOT EXISTS data_quality_checks (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_data_quality_checks_run_id ON data_quality_checks(run_id);

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_data_quality_checks_run_id'
          AND conrelid = 'data_quality_checks'::regclass
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'experiment_runs'
          AND column_name = 'run_id'
    ) THEN
        ALTER TABLE data_quality_checks
            ADD CONSTRAINT fk_data_quality_checks_run_id
            FOREIGN KEY (run_id) REFERENCES experiment_runs(run_id) ON DELETE SET NULL;
    END IF;
END $$;

COMMIT;
