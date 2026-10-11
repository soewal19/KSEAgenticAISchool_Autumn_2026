-- Upgrade databases created by the earlier ORM schema without dropping data.
BEGIN;

-- The previous experiment_runs used id/started_at and stored aggregate metrics.
-- Preserve it, recreate the current shape, then copy a traceable aggregate row.
DO $$ BEGIN
    IF to_regclass('public.experiment_runs') IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'experiment_runs'
             AND column_name = 'started_at'
       )
       AND NOT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'experiment_runs'
             AND column_name = 'dataset_version'
       )
       AND to_regclass('public.experiment_runs_legacy_archive') IS NULL THEN
        ALTER TABLE public.experiment_runs RENAME TO experiment_runs_legacy_archive;
    END IF;
END $$;

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

DO $$ BEGIN
    IF to_regclass('public.experiment_runs_legacy_archive') IS NOT NULL THEN
        INSERT INTO public.experiment_runs (
            run_id, created_at, git_commit, config_hash, dataset_version,
            model_name, forecast_horizon_minutes, train_end, validation_end,
            test_end, metrics_json
        )
        SELECT id, started_at, git_commit, config_hash, 'legacy-migrated',
               'legacy_aggregate', 0,
               COALESCE(train_end, started_at),
               COALESCE(validation_end, train_end, started_at),
               COALESCE(test_end, test_start, finished_at, started_at),
               COALESCE(metrics_json, '{}'::jsonb)
        FROM public.experiment_runs_legacy_archive
        ON CONFLICT (run_id) DO NOTHING;
    END IF;
END $$;

-- Move any legacy raw alert rows into the normalized raw event table.
DO $$ BEGIN
    IF to_regclass('public.alert_events') IS NOT NULL THEN
        INSERT INTO public.raw_alert_events (
            region_id, region_name, alert_start, alert_end, source
        )
        SELECT md5(concat_ws('|', COALESCE(level, ''), COALESCE(oblast, ''),
                             COALESCE(raion, ''), COALESCE(hromada, ''))),
               COALESCE(NULLIF(hromada, ''), NULLIF(raion, ''), oblast),
               started_at, finished_at, COALESCE(source, 'unknown')
        FROM public.alert_events
        WHERE oblast IS NOT NULL AND started_at IS NOT NULL
        ON CONFLICT (region_id, alert_start, source) DO NOTHING;
    END IF;
END $$;

-- Repoint the FK if the legacy table rename moved it to the archive.
DO $$ DECLARE fk_name TEXT; BEGIN
    IF to_regclass('public.data_quality_checks') IS NOT NULL THEN
        FOR fk_name IN
            SELECT c.conname FROM pg_constraint c
            WHERE c.conrelid = 'public.data_quality_checks'::regclass
              AND c.contype = 'f'
              AND c.confrelid <> 'public.experiment_runs'::regclass
        LOOP
            EXECUTE format('ALTER TABLE public.data_quality_checks DROP CONSTRAINT %I', fk_name);
        END LOOP;
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.data_quality_checks'::regclass
              AND confrelid = 'public.experiment_runs'::regclass
              AND contype = 'f'
        ) THEN
            ALTER TABLE public.data_quality_checks
                ADD CONSTRAINT fk_data_quality_checks_run_id
                FOREIGN KEY (run_id) REFERENCES public.experiment_runs(run_id) ON DELETE SET NULL;
        END IF;
    END IF;
END $$;

COMMIT;
