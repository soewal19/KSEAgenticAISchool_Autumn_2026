"""Database-model contract tests that do not require a running PostgreSQL."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.persistence.models import AlertEvent, ExperimentRun


def test_raw_event_schema_has_requested_unique_key_and_utc_columns():
    table = AlertEvent.__table__
    assert set(table.columns.keys()) == {
        "event_id", "region_id", "region_name", "alert_start", "alert_end",
        "source", "loaded_at",
    }
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("region_id", "alert_start", "source") in unique_columns
    assert table.c.alert_start.type.timezone is True
    assert table.c.alert_end.type.timezone is True


def test_experiment_run_schema_keeps_split_provenance_and_metrics():
    columns = set(ExperimentRun.__table__.columns.keys())
    assert {
        "run_id", "config_hash", "dataset_version", "model_name",
        "forecast_horizon_minutes", "train_end", "validation_end", "test_end",
        "pr_auc", "roc_auc", "brier_score", "metrics_json",
    }.issubset(columns)
