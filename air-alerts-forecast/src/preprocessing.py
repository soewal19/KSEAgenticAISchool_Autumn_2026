"""Preprocessing: clean raw intervals and expand them into a regular binary series.

The raw dataset contains alert intervals at three administrative levels
(oblast, raion, hromada). For region-level modelling we keep only
``level == 'oblast'`` rows, which removes the nested duplication.

Each interval (started_at, finished_at) is expanded into a regular
time grid at the configured frequency (default 5 minutes). A grid cell
is 1 if an alert is active during that cell, 0 otherwise.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .logger import get_logger

logger = get_logger("preprocessing")


def clean_intervals(df: pd.DataFrame) -> pd.DataFrame:
    """Clean the raw intervals: filter oblast level, parse times, drop duplicates.

    Args:
        df: Raw DataFrame with columns oblast, level, started_at, finished_at.

    Returns:
        Cleaned DataFrame with one row per oblast alert interval.
    """
    out = df.copy()
    out = out[out["level"] == "oblast"].copy()
    out["started_at"] = pd.to_datetime(out["started_at"], utc=True, errors="coerce")
    out["finished_at"] = pd.to_datetime(out["finished_at"], utc=True, errors="coerce")
    out = out.dropna(subset=["oblast", "started_at", "finished_at"])
    out = out.sort_values(["oblast", "started_at"]).reset_index(drop=True)
    before = len(out)
    out = out.drop_duplicates(subset=["oblast", "started_at", "finished_at"])
    after = len(out)
    logger.info(
        "Cleaned intervals: %d -> %d rows (dropped %d duplicates)",
        before, after, before - after,
    )
    out["duration_min"] = (
        out["finished_at"] - out["started_at"]
    ).dt.total_seconds() / 60.0
    out = out[out["duration_min"] > 0].reset_index(drop=True)
    return out


def build_region_binary_series(
    intervals: pd.DataFrame,
    region: str,
    freq_minutes: int,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.Series:
    """Expand oblast alert intervals for one region into a regular binary series.

    The grid is left-closed: a cell starting at time t is 1 if any alert
    interval overlaps [t, t + freq). Uses interval merging for efficiency.

    Args:
        intervals: Cleaned intervals DataFrame (all regions).
        region: Oblast name to filter on.
        freq_minutes: Grid frequency in minutes.
        start: Optional grid start (default: earliest started_at in region).
        end: Optional grid end (default: latest finished_at in region).

    Returns:
        pd.Series with DatetimeIndex and int8 values (0/1), name = region.
    """
    reg = intervals[intervals["oblast"] == region].copy()
    if reg.empty:
        logger.warning("No intervals found for region %s", region)
        return pd.Series(dtype="int8", name=region)

    starts = reg["started_at"].values
    ends = reg["finished_at"].values
    order = np.argsort(starts)
    starts = starts[order]
    ends = ends[order]

    merged_s: list[np.datetime64] = []
    merged_e: list[np.datetime64] = []
    cur_s, cur_e = starts[0], ends[0]
    for s, e in zip(starts[1:], ends[1:]):
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            merged_s.append(cur_s)
            merged_e.append(cur_e)
            cur_s, cur_e = s, e
    merged_s.append(cur_s)
    merged_e.append(cur_e)

    grid_start = pd.Timestamp(start) if start is not None else pd.Timestamp(starts[0]).floor(f"{freq_minutes}min")
    grid_end = pd.Timestamp(end) if end is not None else pd.Timestamp(ends[-1]).ceil(f"{freq_minutes}min")
    idx = pd.date_range(grid_start, grid_end, freq=f"{freq_minutes}min", inclusive="left")

    values = np.zeros(len(idx), dtype="int8")
    if len(idx) == 0:
        return pd.Series(values, index=idx, name=region, dtype="int8")

    step = np.timedelta64(freq_minutes, "m")
    grid_ns = idx.values.astype("datetime64[ns]")

    for ms, me in zip(merged_s, merged_e):
        left = np.searchsorted(grid_ns, ms - step, side="right")
        right = np.searchsorted(grid_ns, me, side="left")
        if left < right:
            values[left:right] = 1

    logger.info(
        "Region %s: grid %s -> %s (%d cells, alert share %.2f%%)",
        region, grid_start, grid_end, len(idx), 100.0 * values.mean(),
    )
    return pd.Series(values, index=idx, name=region, dtype="int8")


def build_multi_region_frame(
    intervals: pd.DataFrame,
    regions: Iterable[str],
    freq_minutes: int,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build a wide DataFrame of binary alert series for multiple regions.

    Args:
        intervals: Cleaned intervals DataFrame.
        regions: Iterable of oblast names.
        freq_minutes: Grid frequency in minutes.
        start: Common grid start.
        end: Common grid end.

    Returns:
        DataFrame with one column per region and a regular DatetimeIndex.
    """
    regions = list(regions)
    if start is None or end is None:
        all_starts = intervals["started_at"]
        all_ends = intervals["finished_at"]
        if start is None:
            start = all_starts.min().floor(f"{freq_minutes}min")
        if end is None:
            end = all_ends.max().ceil(f"{freq_minutes}min")
    series = {}
    for r in regions:
        series[r] = build_region_binary_series(intervals, r, freq_minutes, start, end)
    frame = pd.DataFrame(series)
    return frame
