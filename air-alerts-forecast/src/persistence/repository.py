"""Idempotent repository for optional PostgreSQL provenance and alert records."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .models import AlertEvent, Base, CleanedInterval, DataQualityCheck, ExperimentRun
from .settings import PersistenceSettings


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        ts = pd.Timestamp(value)
        return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _hash_row(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    normalized = {}
    for field in fields:
        value = row.get(field)
        if value is None or pd.isna(value):
            normalized[field] = None
        elif field.endswith("_at"):
            ts = pd.Timestamp(value)
            normalized[field] = (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).isoformat()
        else:
            normalized[field] = str(value)
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


class PersistenceRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def upsert_alert_events(self, frame: pd.DataFrame) -> int:
        records = []
        for raw in frame.to_dict(orient="records"):
            def present(value: Any) -> bool:
                return value is not None and not pd.isna(value) and bool(str(value).strip())

            oblast = str(raw["oblast"]) if present(raw.get("oblast")) else ""
            raion = str(raw["raion"]) if present(raw.get("raion")) else ""
            hromada = str(raw["hromada"]) if present(raw.get("hromada")) else ""
            level = str(raw["level"]) if present(raw.get("level")) else "oblast"
            region_name = hromada or raion or oblast
            if not region_name:
                continue
            # PostgreSQL's built-in md5() uses the same stable composite key
            # in the legacy-data migration; this is an identifier, not a secret.
            region_key = "|".join((level, oblast, raion, hromada)).encode("utf-8")
            region_id = hashlib.md5(region_key, usedforsecurity=False).hexdigest()

            def utc_timestamp(value: Any) -> pd.Timestamp | None:
                if value is None:
                    return None
                timestamp = pd.to_datetime(value, utc=True, errors="coerce")
                return None if pd.isna(timestamp) else timestamp

            alert_start = utc_timestamp(raw.get("started_at", raw.get("alert_start")))
            if alert_start is None:
                continue
            alert_end = utc_timestamp(raw.get("finished_at", raw.get("alert_end")))
            row = {
                "region_id": region_id,
                "region_name": region_name,
                "alert_start": alert_start,
                "alert_end": alert_end,
                "source": str(raw["source"]) if present(raw.get("source")) else "unknown",
            }
            records.append(row)
        return self._insert_ignore(
            AlertEvent, records, ("region_id", "alert_start", "source")
        )

    def upsert_cleaned_intervals(self, frame: pd.DataFrame) -> int:
        fields = ("oblast", "started_at", "finished_at", "duration_min", "source")
        records = []
        for raw in frame.to_dict(orient="records"):
            row = {field: _json_safe(raw.get(field)) for field in fields}
            for field in ("started_at", "finished_at"):
                ts = pd.Timestamp(row[field])
                row[field] = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
            row["interval_hash"] = _hash_row(row, fields)
            records.append(row)
        return self._insert_ignore(CleanedInterval, records, "interval_hash")

    def _insert_ignore(self, model: type, records: list[dict], key: str | tuple[str, ...]) -> int:
        if not records:
            return 0
        inserted = 0
        with self.engine.begin() as conn:
            # Keep each statement below PostgreSQL's bind-parameter limits for
            # the full national source dataset.
            for offset in range(0, len(records), 500):
                batch = records[offset : offset + 500]
                index_elements = [key] if isinstance(key, str) else list(key)
                stmt = insert(model).values(batch).on_conflict_do_nothing(index_elements=index_elements).returning(model.event_id if model is AlertEvent else model.id)
                inserted += len(conn.execute(stmt).all())
        return inserted

    def record_quality_checks(self, checks: list[dict[str, Any]], run_id: uuid.UUID | None = None) -> None:
        with Session(self.engine) as session, session.begin():
            session.add_all([
                DataQualityCheck(run_id=run_id, check_name=item["check_name"], passed=bool(item["passed"]), details_json=item.get("details_json", {}))
                for item in checks
            ])

    def record_experiment_run(self, *, run_id: uuid.UUID, config_hash: str,
                              git_commit: str | None, dataset_version: str,
                              model_name: str, forecast_horizon_minutes: int,
                              train_end: datetime, validation_end: datetime,
                              test_end: datetime, metrics: dict[str, Any]) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(ExperimentRun(
                run_id=run_id, config_hash=config_hash, git_commit=git_commit,
                dataset_version=dataset_version, model_name=model_name,
                forecast_horizon_minutes=forecast_horizon_minutes,
                train_end=train_end, validation_end=validation_end, test_end=test_end,
                pr_auc=metrics.get("pr_auc"), roc_auc=metrics.get("roc_auc"),
                brier_score=metrics.get("brier"), metrics_json=_json_safe(metrics),
            ))


def get_repository() -> PersistenceRepository | None:
    """Return a repository only when DATABASE_URL is configured (offline-safe)."""
    url = PersistenceSettings().sqlalchemy_url
    if not url:
        return None
    return PersistenceRepository(create_engine(url, pool_pre_ping=True))
