"""Run logging for auditability and reproducibility.

Every pipeline run produces a JSON artifact recording:
  - run_id (timestamp-based unique id)
  - timestamp (UTC ISO)
  - config_hash (SHA-256 of the resolved config)
  - data_range (first/last timestamp of the feature matrix)
  - feature_names (list of feature columns)
  - model (name of the best model)
  - metrics (test metrics dict)

Logs are written to ``outputs/runs/<run_id>.json``.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import AppConfig


class RunLog(BaseModel):
    """Structured record of a single pipeline run."""

    run_id: str
    timestamp: str
    config_hash: str
    data_range: dict[str, str]
    n_rows: int
    feature_names: list[str]
    target_region: str
    horizon_minutes: int
    models_evaluated: list[str]
    best_model: str
    metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)


def config_hash(config: AppConfig) -> str:
    """Stable SHA-256 hash of the serialized config for reproducibility."""
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def make_run_id() -> str:
    """Generate a short, sortable run id: YYYYMMDD-HHMMSS-<short-uuid>."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:6]}"


def build_run_log(
    config: AppConfig,
    feature_names: list[str],
    n_rows: int,
    data_min: str,
    data_max: str,
    best_model: str,
    models_evaluated: list[str],
    metrics: dict[str, dict[str, float]],
) -> RunLog:
    return RunLog(
        run_id=make_run_id(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        config_hash=config_hash(config),
        data_range={"min": data_min, "max": data_max},
        n_rows=n_rows,
        feature_names=feature_names,
        target_region=config.regions.target,
        horizon_minutes=config.time.horizon_minutes,
        models_evaluated=models_evaluated,
        best_model=best_model,
        metrics=metrics,
    )


def save_run_log(run_log: RunLog, output_dir: str | Path = "outputs/runs") -> Path:
    """Persist the run log to ``outputs/runs/<run_id>.json`` and return the path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{run_log.run_id}.json"
    path.write_text(
        json.dumps(run_log.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
