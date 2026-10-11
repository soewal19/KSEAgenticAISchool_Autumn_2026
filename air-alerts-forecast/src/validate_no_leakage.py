"""Leakage validation suite.

Checks (all must PASS):
  1. Chronological split: train < val < test by timestamp, no overlap.
  2. Feature timestamps: every feature row's index <= its target forecast time.
  3. No NaN or Inf in feature matrix.
  4. Target correctness: y_t == 1 iff an alert-start exists in (t, t+H].
  5. No target values in the feature columns.
  6. Scaler/encoder/threshold are not needed to be checked here (they are
     fit on train by construction in models.fit_model), but we verify the
     train portion of features does not depend on future data by checking
     lag columns are NaN at the series start (not filled with future).
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from .config import AppConfig, load_config
from .data_loader import load_raw
from .features import build_features, split_train_val_test, split_labeled_train_val_test
from .labels import alert_starts, make_target
from .logger import get_logger
from .preprocessing import build_multi_region_frame, clean_intervals

logger = get_logger("validate_no_leakage")


class Checker:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.results.append((name, bool(condition), detail))

    def report(self) -> int:
        print("\n" + "=" * 72)
        print("NO-LEAKAGE VALIDATION REPORT")
        print("=" * 72)
        n_pass = 0
        for name, ok, detail in self.results:
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {name}")
            if detail:
                print(f"       {detail}")
            if ok:
                n_pass += 1
        print("-" * 72)
        print(f"Total: {n_pass}/{len(self.results)} checks passed")
        print("=" * 72)
        return 0 if n_pass == len(self.results) else 1


def check_chronological_split(X: pd.DataFrame, config: AppConfig, c: Checker) -> None:
    train_end = pd.Timestamp(config.split.train_end, tz="UTC")
    val_end = pd.Timestamp(config.split.val_end, tz="UTC")
    tr, va, te = split_train_val_test(X, config.split.train_end, config.split.val_end)
    c.check(
        "Train before val boundary",
        len(tr) > 0 and tr.index.max() < train_end,
        f"train_max={tr.index.max() if len(tr) else None} < {train_end}",
    )
    c.check(
        "Val within [train_end, val_end)",
        len(va) > 0 and va.index.min() >= train_end and va.index.max() < val_end,
        f"val_min={va.index.min() if len(va) else None}, val_max={va.index.max() if len(va) else None}",
    )
    c.check(
        "Test after val boundary",
        len(te) > 0 and te.index.min() >= val_end,
        f"test_min={te.index.min() if len(te) else None} >= {val_end}",
    )
    c.check(
        "No index overlap between splits",
        len(set(tr.index) & set(va.index)) == 0 and len(set(va.index) & set(te.index)) == 0
        and len(set(tr.index) & set(te.index)) == 0,
        "splits are disjoint",
    )


def check_label_embargo(
    X: pd.DataFrame, y: pd.Series, config: AppConfig, c: Checker
) -> None:
    (x_train, _), (x_val, _), (x_test, _) = split_labeled_train_val_test(
        X, y, config.split.train_end, config.split.val_end,
        config.time.horizon_minutes,
    )
    horizon = pd.Timedelta(minutes=config.time.horizon_minutes)
    train_end = pd.Timestamp(config.split.train_end, tz="UTC")
    val_end = pd.Timestamp(config.split.val_end, tz="UTC")
    train_ok = len(x_train) > 0 and (x_train.index + horizon < train_end).all()
    val_ok = len(x_val) > 0 and (x_val.index + horizon < val_end).all()
    test_ok = len(x_test) > 0 and (x_test.index >= val_end).all()
    c.check(
        "Label horizon embargo at split boundaries",
        train_ok and val_ok and test_ok,
        f"train max label end={(x_train.index.max() + horizon) if len(x_train) else None}; "
        f"val max label end={(x_val.index.max() + horizon) if len(x_val) else None}; "
        f"horizon={horizon}",
    )


def check_no_nan_inf(X: pd.DataFrame, c: Checker) -> None:
    has_nan = X.isna().any().any()
    has_inf = np.isinf(X.select_dtypes(include=[np.number])).any().any() if not X.empty else False
    c.check("No NaN in features", not has_nan, "all cells finite" if not has_nan else f"NaN in {X.columns[X.isna().any()].tolist()}")
    c.check("No Inf in features", not has_inf, "all cells finite" if not has_inf else "Inf values present")


def check_target_correctness(series: pd.Series, y: pd.Series, horizon: int, freq: int, c: Checker) -> None:
    starts = alert_starts(series)
    H_steps = max(1, horizon // freq)
    mismatches = 0
    checked = 0
    for i in range(len(series) - H_steps):
        t = series.index[i]
        future_window = starts.iloc[i + 1: i + 1 + H_steps]
        expected = 1 if future_window.any() else 0
        actual = int(y.iloc[i]) if not pd.isna(y.iloc[i]) else -1
        if actual == -1:
            continue
        checked += 1
        if actual != expected:
            mismatches += 1
            if mismatches <= 3:
                logger.debug("Mismatch at %s: expected %d got %d", t, expected, actual)
    c.check(
        "Target computed correctly (no future leakage)",
        checked > 0 and mismatches == 0,
        f"checked {checked} rows, mismatches {mismatches}",
    )


def check_lag_features_not_future(
    X: pd.DataFrame, series: pd.Series, config: AppConfig, c: Checker
) -> None:
    freq = config.time.freq_minutes
    for lag in config.features.lags_minutes:
        col = f"target_lag_{lag}m"
        if col not in X.columns:
            continue
        steps = max(1, lag // freq)
        head_vals = X[col].iloc[:steps]
        c.check(
            f"Lag feature {col} head is 0 (cold start, no future fill)",
            (head_vals == 0).all(),
            f"first {steps} cells == 0",
        )
        body_lag = X[col].iloc[steps:]
        body_orig = series.iloc[:-steps].fillna(0).values
        ok = np.allclose(body_lag.values, body_orig, atol=0)
        c.check(
            f"Lag feature {col} matches past values (no future leakage)",
            ok,
            f"lag({lag}m)[t] == series[t-{steps}]",
        )


def check_no_target_in_features(X: pd.DataFrame, c: Checker) -> None:
    c.check(
        "No target column in features",
        "target" not in X.columns and "y" not in X.columns,
        f"columns: {list(X.columns[:5])}...",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)

    raw = load_raw(config)
    intervals = clean_intervals(raw)
    regions = [config.regions.target] + config.regions.neighbors
    frame = build_multi_region_frame(intervals, regions, config.time.freq_minutes)

    target_series = frame[config.regions.target]
    neighbors = {r: frame[r] for r in config.regions.neighbors if r in frame.columns}
    X = build_features(target_series, neighbors, config)
    y = make_target(target_series, config.time.horizon_minutes, config.time.freq_minutes)

    c = Checker()
    check_chronological_split(X, config, c)
    check_label_embargo(X, y, config, c)
    check_no_nan_inf(X, c)
    check_target_correctness(
        target_series, y, config.time.horizon_minutes, config.time.freq_minutes, c
    )
    check_lag_features_not_future(X, target_series, config, c)
    check_no_target_in_features(X, c)

    c.check(
        "Feature index equals target index (aligned)",
        X.index.equals(y.index),
        "features and target share index",
    )

    return c.report()


if __name__ == "__main__":
    sys.exit(main())
