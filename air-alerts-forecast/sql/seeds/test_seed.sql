-- Synthetic rows for a disposable local PostgreSQL / Neon test branch only.
-- Idempotent: safe to apply repeatedly; these are not real alert observations.
BEGIN;

INSERT INTO raw_alert_events
    (region_id, region_name, alert_start, alert_end, source)
VALUES
    ('seed-kyiv-city', 'Kyiv City', '2024-01-01 00:00:00+00', '2024-01-01 00:15:00+00', 'sql-test-seed'),
    ('seed-kyivska', 'Kyivska oblast', '2024-01-01 00:30:00+00', '2024-01-01 00:45:00+00', 'sql-test-seed'),
    ('seed-chernihivska', 'Chernihivska oblast', '2024-01-01 01:00:00+00', '2024-01-01 01:15:00+00', 'sql-test-seed')
ON CONFLICT (region_id, alert_start, source) DO NOTHING;

INSERT INTO cleaned_intervals
    (oblast, started_at, finished_at, duration_min, source, interval_hash)
VALUES
    ('Kyiv City', '2024-01-01 00:00:00+00', '2024-01-01 00:15:00+00', 15.0,
     'sql-test-seed', 'seed-interval-kyiv-city-20240101T0000Z')
ON CONFLICT (interval_hash) DO NOTHING;

INSERT INTO experiment_runs (
    run_id, git_commit, config_hash, dataset_version, model_name,
    forecast_horizon_minutes, train_end, validation_end, test_end,
    pr_auc, roc_auc, brier_score, metrics_json
)
VALUES (
    '00000000-0000-4000-8000-000000000001', NULL, 'seed-config-v1',
    'synthetic-test-fixture-v1', 'persistence', 30,
    '2024-01-05 00:00:00+00', '2024-01-09 00:00:00+00', '2024-01-12 00:00:00+00',
    0.12, 0.46, 0.14,
    '{"note":"synthetic SQL test seed; not a real experiment","n":1125}'::jsonb
)
ON CONFLICT (run_id) DO NOTHING;

INSERT INTO data_quality_checks (run_id, check_name, passed, details_json)
SELECT '00000000-0000-4000-8000-000000000001', 'seed_fixture_is_synthetic', true,
       '{"source":"sql-test-seed"}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM data_quality_checks
    WHERE run_id = '00000000-0000-4000-8000-000000000001'
      AND check_name = 'seed_fixture_is_synthetic'
);

COMMIT;
