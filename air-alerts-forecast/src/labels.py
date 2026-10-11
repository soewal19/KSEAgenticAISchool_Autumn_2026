"""Target (label) construction for binary alert-start forecasting.

Target definition (strictly causal, no leakage):
    y_t = 1  iff  a NEW alert starts in the region during (t, t + H]
where H is the forecast horizon (configurable: 15, 30, 60 minutes).

A "new alert start" is detected as a transition from 0 -> 1 in the
binary series. If an alert is already active at t, we look for a
NEW start after the current one ends within the horizon; for simplicity
and following the Pavlyshenko formulation, we flag any 0->1 transition
whose start time lies in (t, t+H].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .logger import get_logger

logger = get_logger("labels")


def alert_starts(series: pd.Series) -> pd.Series:
    """Return a boolean series that is True at the first cell of each alert.

    A start is detected where the value transitions from 0 (or NaN/leading)
    to 1.

    Args:
        series: Binary alert series (0/1) with DatetimeIndex.

    Returns:
        Boolean Series aligned to the same index.
    """
    s = series.fillna(0).astype(int)
    prev = s.shift(1).fillna(0).astype(int)
    starts = (s == 1) & (prev == 0)
    return starts


def make_target(
    series: pd.Series,
    horizon_minutes: int,
    freq_minutes: int,
) -> pd.Series:
    """Compute y_t: 1 if a new alert starts in (t, t + horizon_minutes].

    Uses a forward-looking rolling sum over the alert-start indicator.
    The current cell t is EXCLUDED (strictly future window (t, t+H]).

    Implementation: backward rolling sum of starts shifted by H steps,
    so position t holds sum(starts[t+1 .. t+H]).

    Args:
        series: Binary alert series (0/1).
        horizon_minutes: Forecast horizon H in minutes.
        freq_minutes: Grid frequency in minutes.

    Returns:
        Series of 0/1 targets aligned to the input index. The last
        H cells are NaN because the future window is not fully observed.
    """
    starts = alert_starts(series).astype(int)
    steps = max(1, horizon_minutes // freq_minutes)
    forward_sum = (
        starts.rolling(window=steps, min_periods=steps).sum().shift(-steps)
    )
    target = (forward_sum >= 1).astype("float")
    target[forward_sum.isna()] = np.nan
    n_na = int(target.isna().sum())
    logger.info(
        "Target H=%d min: %d rows, %d positive (%.3f%%), %d NaN tail",
        horizon_minutes,
        len(target),
        int(target.sum()),
        100.0 * target.mean(),
        n_na,
    )
    return target
