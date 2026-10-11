"""Feature engineering for alert-start forecasting.

All features are constructed strictly from information available at or
before time t. No feature uses future observations. Key invariants:

* lags use ``series.shift(k)`` with k >= 1 (past cells only);
* rolling counts use backward-looking windows ending at t-1;
* current-alert duration and time-since-last are derived from past and
  present state only;
* calendar features are deterministic functions of the timestamp t.

A feature matrix produced here can be safely used with the target from
``labels.make_target`` without leakage, as long as row t of features is
paired with row t of the target (target looks forward, features look
backward).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AppConfig
from .logger import get_logger

logger = get_logger("features")

WAR_START = pd.Timestamp("2022-02-24", tz="UTC")


def _as_int_steps(minutes: int, freq_minutes: int) -> int:
    return max(1, int(round(minutes / freq_minutes)))


def add_lag_features(
    df: pd.DataFrame,
    series: pd.Series,
    lags_minutes: list[int],
    freq_minutes: int,
    prefix: str,
) -> pd.DataFrame:
    """Add lag features of a binary series (strictly past, shift >= 1)."""
    for lag in lags_minutes:
        steps = _as_int_steps(lag, freq_minutes)
        df[f"{prefix}_lag_{lag}m"] = series.shift(steps).astype("float")
    return df


def add_rolling_alert_counts(
    df: pd.DataFrame,
    starts: pd.Series,
    windows_minutes: dict[str, int],
    freq_minutes: int,
) -> pd.DataFrame:
    """Add backward rolling counts of alert starts in past windows.

    The window is [t - W, t) so it strictly excludes the current cell.
    """
    for name, win in windows_minutes.items():
        steps = _as_int_steps(win, freq_minutes)
        shifted = starts.shift(1)
        df[f"starts_count_{name}"] = (
            shifted.rolling(window=steps, min_periods=1, closed="left").sum().astype("float")
        )
    return df


def add_current_alert_duration(
    df: pd.DataFrame,
    series: pd.Series,
    freq_minutes: int,
) -> pd.DataFrame:
    """Add duration (in minutes) of the currently active alert, else 0.

    Computed from consecutive run-lengths of 1s ending at t; uses only
    present and past values.
    """
    s = series.fillna(0).astype(int)
    group = (s != s.shift()).cumsum()
    run_len = s.groupby(group).cumcount() + 1
    df["current_alert_duration_min"] = np.where(s == 1, run_len * freq_minutes, 0).astype("float")
    return df


def add_time_since_last_alert(
    df: pd.DataFrame,
    series: pd.Series,
    freq_minutes: int,
) -> pd.DataFrame:
    """Minutes since the end of the previous alert (0 if currently active).

    For cells with no prior alert, set to minutes since series start.
    Uses only past values.
    """
    s = series.fillna(0).astype(int)
    ends = (s == 0) & (s.shift(1).fillna(0) == 1)
    last_end_idx = pd.Series(np.nan, index=s.index, dtype="float64")
    last_end_idx[ends] = np.arange(len(s))[ends.values]
    last_end_idx = last_end_idx.ffill()
    elapsed = (np.arange(len(s)) - last_end_idx) * freq_minutes
    elapsed = elapsed.fillna(pd.Series(np.arange(len(s)) * freq_minutes, index=s.index))
    df["time_since_last_alert_min"] = np.where(s == 1, 0, elapsed).astype("float")
    return df


def add_calendar_features(df: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Add deterministic calendar features derived from timestamp t."""
    df["hour"] = index.hour.astype("float")
    df["dayofweek"] = index.dayofweek.astype("float")
    df["month"] = index.month.astype("float")
    df["is_weekend"] = (index.dayofweek >= 5).astype("float")
    df["days_since_war_start"] = (index - WAR_START).total_seconds() / 86400.0

    df["hour_sin"] = np.sin(2 * np.pi * index.hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * index.hour / 24.0)
    df["dow_sin"] = np.sin(2 * np.pi * index.dayofweek / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * index.dayofweek / 7.0)
    return df


def build_features(
    target_series: pd.Series,
    neighbor_series: dict[str, pd.Series],
    config: AppConfig,
) -> pd.DataFrame:
    """Build the full feature matrix for the target region.

    Args:
        target_series: Binary alert series for the target region.
        neighbor_series: Dict of neighbor region name -> binary series.
        config: Application configuration.

    Returns:
        DataFrame indexed by the target series DatetimeIndex with all
        features. Target column is NOT included here.
    """
    freq = config.time.freq_minutes
    idx = target_series.index
    df = pd.DataFrame(index=idx)

    add_lag_features(df, target_series, config.features.lags_minutes, freq, "target")
    add_current_alert_duration(df, target_series, freq)
    add_time_since_last_alert(df, target_series, freq)

    from .labels import alert_starts
    starts = alert_starts(target_series).astype(int)
    add_rolling_alert_counts(df, starts, config.features.rolling_windows, freq)

    for name, s in neighbor_series.items():
        safe = name.replace(" ", "_").replace("'", "")
        add_lag_features(df, s, config.features.lags_minutes, freq, f"nb_{safe}")

    add_calendar_features(df, idx)

    df = df.fillna(0.0)

    logger.info("Built feature matrix: %d rows x %d columns", len(df), len(df.columns))
    return df


def split_train_val_test(
    df: pd.DataFrame,
    train_end: str,
    val_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological train/val/test split. No shuffling.

    Args:
        df: Feature DataFrame with DatetimeIndex.
        train_end: Exclusive end date for train (e.g. '2023-12-31').
        val_end: Exclusive end date for validation.

    Returns:
        (train, val, test) DataFrames.
    """
    train = df[df.index < pd.Timestamp(train_end, tz="UTC")]
    val = df[(df.index >= pd.Timestamp(train_end, tz="UTC")) & (df.index < pd.Timestamp(val_end, tz="UTC"))]
    test = df[df.index >= pd.Timestamp(val_end, tz="UTC")]
    logger.info(
        "Split sizes: train=%d, val=%d, test=%d", len(train), len(val), len(test)
    )
    return train, val, test


def split_labeled_train_val_test(
    X: pd.DataFrame,
    y: pd.Series,
    train_end: str,
    val_end: str,
    horizon_minutes: int,
) -> tuple[tuple[pd.DataFrame, pd.Series], tuple[pd.DataFrame, pd.Series], tuple[pd.DataFrame, pd.Series]]:
    """Split aligned rows and purge labels whose forward window crosses a cutoff.

    The target at ``t`` observes outcomes in ``(t, t + horizon]``. A row is
    retained only when that full window ends strictly before the next split.
    Rows with unknown targets are excluded from all returned partitions.
    """
    if not X.index.equals(y.index):
        raise ValueError("Feature and target indexes must be identical")
    train_cut = pd.Timestamp(train_end)
    val_cut = pd.Timestamp(val_end)
    train_cut = train_cut.tz_localize("UTC") if train_cut.tzinfo is None else train_cut.tz_convert("UTC")
    val_cut = val_cut.tz_localize("UTC") if val_cut.tzinfo is None else val_cut.tz_convert("UTC")
    horizon = pd.Timedelta(minutes=horizon_minutes)
    idx = X.index
    known = y.notna()
    train_mask = (idx + horizon < train_cut) & known.to_numpy()
    val_mask = (idx >= train_cut) & (idx + horizon < val_cut) & known.to_numpy()
    test_mask = (idx >= val_cut) & known.to_numpy()

    def select(mask: np.ndarray) -> tuple[pd.DataFrame, pd.Series]:
        return X.loc[mask], y.loc[mask].astype(int)

    splits = select(train_mask), select(val_mask), select(test_mask)
    logger.info("Embargoed labeled split sizes: train=%d, val=%d, test=%d",
                len(splits[0][0]), len(splits[1][0]), len(splits[2][0]))
    return splits
