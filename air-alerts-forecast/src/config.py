"""Pydantic configuration model for air-alerts-forecast."""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    source_url: str
    raw_path: str
    war_start: str


class RegionsConfig(BaseModel):
    target: str
    neighbors: List[str]


class TimeConfig(BaseModel):
    freq_minutes: int = Field(ge=1)
    horizon_minutes: int = Field(ge=1)
    horizons_to_eval: List[int]


class FeaturesConfig(BaseModel):
    lags_minutes: List[int]
    rolling_windows: dict


class SplitConfig(BaseModel):
    train_end: str
    val_end: str


class ThresholdConfig(BaseModel):
    metric: str
    min_recall: float = Field(ge=0.0, le=1.0)


class OutputsConfig(BaseModel):
    figures_dir: str
    metrics_dir: str
    predictions_dir: str
    metrics_filename: str = "test_metrics.json"


class ProjectConfig(BaseModel):
    name: str
    random_state: int
    log_level: str


class AppConfig(BaseModel):
    project: ProjectConfig
    data: DataConfig
    regions: RegionsConfig
    time: TimeConfig
    features: FeaturesConfig
    split: SplitConfig
    models: List[str]
    threshold: ThresholdConfig
    outputs: OutputsConfig


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Load and validate the YAML configuration into a Pydantic model."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig(**raw)
