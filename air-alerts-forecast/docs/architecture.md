# Architecture and Optional Persistence

The project is a single-process Python research pipeline. Its data flow and module responsibilities are documented in the [C4 architecture](C4.md). The application can run from local files without PostgreSQL; Neon is an optional persistence adapter.

## Storage boundaries

| Data | Storage | Reason |
|---|---|---|
| Raw alert events | PostgreSQL table raw_alert_events | Compact event records with a uniqueness key for repeatable ingestion |
| Cleaned alert intervals | PostgreSQL table cleaned_intervals | Compact, deduplicated interval records |
| Experiment metadata and metrics | PostgreSQL table experiment_runs | Queryable model, split, dataset-version, and metric provenance |
| Data-quality results | PostgreSQL table data_quality_checks | Queryable audit records, optionally associated with a run |
| Minute-level regional series, feature matrices, and predictions | Parquet under outputs/ | Dense arrays are better stored as columnar local files than event rows in PostgreSQL |

## Persistence flow

1. The YAML config is loaded and validated.
2. If DATABASE_URL is missing, no database engine is created and the pipeline proceeds with its normal local files.
3. If DATABASE_URL is present, pydantic-settings reads it and SQLAlchemy connects through psycopg.
4. Raw events are mapped to a stable region identifier and inserted with conflict handling on (region_id, alert_start, source). Re-running the loader does not create duplicate events.
5. Cleaned intervals are loaded with their deterministic interval hash. Data-quality checks are recorded as JSONB details.
6. At evaluation, one experiment_runs record is written for each evaluated model. dataset_version is the SHA-256 digest of the loaded raw rows; split boundaries and metrics are retained.

All event and split timestamps are timezone-aware and stored as PostgreSQL TIMESTAMPTZ. Credentials are read from DATABASE_URL and must stay outside source control.

## Schema changes

Apply SQL files under sql/migrations in numeric order. Migration 001 creates the current schema. Migration 002 upgrades the earlier schema and preserves historic run data in experiment_runs_legacy_archive while moving available events and run identifiers forward.

The SQLAlchemy models describe the current schema, but create_all does not alter existing tables. Apply migrations before using a database that contains the earlier schema. The synthetic seed in sql/seeds/test_seed.sql is for a disposable local database or a dedicated test branch only.

## Runtime and CI

The Docker image uses Python 3.11, a multi-stage dependency build, and a non-root runtime user. Docker Compose provides only an optional local PostgreSQL service. CI runs tests, leakage validation, image build, and a full pipeline smoke run against the small fixed fixture. It does not publish or deploy an image.

## Out of scope

The persistence adapter does not store minute-level matrices, serve an API, schedule recurring forecasts, or deploy a model. These are separate concerns and are not required for the research assignment.
