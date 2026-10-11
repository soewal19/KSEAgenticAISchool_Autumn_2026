"""Tests for the air-alert forecasting pipeline.

These tests verify correctness of core data transformations and the
no-leakage invariants. They use a small synthetic interval dataset so
they run quickly without network access.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.labels import alert_starts, make_target
from src.preprocessing import build_region_binary_series, clean_intervals


@pytest.fixture
def synthetic_intervals() -> pd.DataFrame:
    """A tiny synthetic intervals DataFrame with oblast-level rows."""
    return pd.DataFrame({
        "oblast": ["Kyiv City", "Kyiv City", "Kyivska oblast"],
        "raion": [None, None, None],
        "hromada": [None, None, None],
        "level": ["oblast", "oblast", "oblast"],
        "started_at": [
            "2022-03-15 16:00:00+00:00",
            "2022-03-15 17:00:00+00:00",
            "2022-03-15 16:30:00+00:00",
        ],
        "finished_at": [
            "2022-03-15 16:30:00+00:00",
            "2022-03-15 17:20:00+00:00",
            "2022-03-15 17:00:00+00:00",
        ],
        "source": ["official"] * 3,
    })


def test_clean_intervals_filters_oblast_and_parses_times(synthetic_intervals):
    df = clean_intervals(synthetic_intervals)
    assert (df["level"] == "oblast").all()
    assert pd.api.types.is_datetime64_any_dtype(df["started_at"])
    assert "duration_min" in df.columns
    assert (df["duration_min"] > 0).all()


def test_clean_intervals_removes_duplicates():
    df = pd.DataFrame({
        "oblast": ["Kyiv City"] * 3,
        "raion": [None] * 3,
        "hromada": [None] * 3,
        "level": ["oblast"] * 3,
        "started_at": ["2022-03-15 16:00:00+00:00"] * 3,
        "finished_at": ["2022-03-15 16:30:00+00:00"] * 3,
        "source": ["official"] * 3,
    })
    cleaned = clean_intervals(df)
    assert len(cleaned) == 1


def test_binary_series_expansion(synthetic_intervals):
    cleaned = clean_intervals(synthetic_intervals)
    series = build_region_binary_series(
        cleaned, "Kyiv City", freq_minutes=5,
        start=pd.Timestamp("2022-03-15 16:00:00+00:00"),
        end=pd.Timestamp("2022-03-15 17:30:00+00:00"),
    )
    assert series.dtype == "int8"
    assert set(series.unique()).issubset({0, 1})
    assert series.sum() > 0
    expected_active = pd.Timestamp("2022-03-15 16:00:00+00:00")
    assert series.loc[expected_active] == 1


def test_alert_starts_detects_transitions():
    s = pd.Series([0, 0, 1, 1, 0, 1, 0])
    starts = alert_starts(s)
    assert list(starts.astype(int)) == [0, 0, 1, 0, 0, 1, 0]


def test_make_target_is_forward_looking():
    s = pd.Series([0, 0, 1, 0, 0, 1, 0, 0])
    y = make_target(s, horizon_minutes=10, freq_minutes=5)
    assert y.iloc[1] == 1
    assert y.iloc[3] == 1
    assert pd.isna(y.iloc[-2])


def test_make_target_excludes_current_cell():
    s = pd.Series([1, 0, 0, 0])
    y = make_target(s, horizon_minutes=5, freq_minutes=5)
    assert y.iloc[0] == 0


def test_chronological_split():
    from src.features import split_train_val_test
    idx = pd.date_range("2023-01-01", periods=365, freq="D", tz="UTC")
    df = pd.DataFrame({"x": range(365)}, index=idx)
    tr, va, te = split_train_val_test(df, "2023-04-01", "2023-07-01")
    assert tr.index.max() < pd.Timestamp("2023-04-01", tz="UTC")
    assert va.index.min() >= pd.Timestamp("2023-04-01", tz="UTC")
    assert te.index.min() >= pd.Timestamp("2023-07-01", tz="UTC")
    assert len(set(tr.index) & set(va.index)) == 0
    assert len(set(va.index) & set(te.index)) == 0


def test_lag_features_use_past_only():
    from src.config import AppConfig
    from src.features import build_features
    idx = pd.date_range("2022-03-15", periods=100, freq="5min", tz="UTC")
    target = pd.Series(np.random.randint(0, 2, 100), index=idx, name="target")
    neighbors = {"Kyivska oblast": pd.Series(np.random.randint(0, 2, 100), index=idx)}
    import yaml
    cfg = AppConfig(**yaml.safe_load(Path("config.yaml").read_text()))
    X = build_features(target, neighbors, cfg)
    assert "target" not in X.columns
    assert not X.isna().any().any()
    assert np.isfinite(X.select_dtypes(include=[np.number])).all().all()
    assert X["target_lag_5m"].iloc[0] == 0
