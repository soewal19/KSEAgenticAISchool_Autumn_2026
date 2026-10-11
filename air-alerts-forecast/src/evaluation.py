"""Evaluation metrics and reporting.

Primary metric: PR-AUC (severe class imbalance).
Also reports: ROC-AUC, precision/recall/F1 at val-selected threshold,
Brier score, calibration curve, confusion matrix, lift over persistence,
permutation importance, degradation-over-time, and error examples.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .logger import get_logger

logger = get_logger("evaluation")


def compute_metrics(
    y_true: np.ndarray,
    proba: np.ndarray,
    threshold: float,
    persistence_proba: np.ndarray | None = None,
) -> dict:
    """Compute the full metric suite for one model.

    Args:
        y_true: True labels.
        proba: Predicted probabilities for class 1.
        threshold: Decision threshold (selected on validation).
        persistence_proba: Persistence baseline probabilities for lift.

    Returns:
        Dictionary of metrics.
    """
    pred = (proba >= threshold).astype(int)
    metrics: dict = {}
    metrics["n"] = int(len(y_true))
    metrics["positives"] = int(y_true.sum())
    metrics["base_rate"] = float(y_true.mean())
    metrics["pr_auc"] = float(average_precision_score(y_true, proba))
    metrics["roc_auc"] = float(roc_auc_score(y_true, proba))
    metrics["precision"] = float(precision_score(y_true, pred, zero_division=0))
    metrics["recall"] = float(recall_score(y_true, pred, zero_division=0))
    metrics["f1"] = float(f1_score(y_true, pred, zero_division=0))
    metrics["brier"] = float(brier_score_loss(y_true, proba))
    metrics["threshold"] = float(threshold)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    metrics["confusion_matrix"] = {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
    metrics["fpr"] = float(fp / max(1, fp + tn))

    if persistence_proba is not None:
        pers_pred = (persistence_proba >= 0.5).astype(int)
        pers_f1 = f1_score(y_true, pers_pred, zero_division=0)
        metrics["persistence_f1"] = float(pers_f1)
        metrics["lift_over_persistence_f1"] = float(metrics["f1"] / pers_f1) if pers_f1 > 0 else None
        pers_pr = average_precision_score(y_true, persistence_proba)
        metrics["persistence_pr_auc"] = float(pers_pr)
        metrics["lift_over_persistence_pr_auc"] = float(metrics["pr_auc"] / pers_pr) if pers_pr > 0 else None

    return metrics


def calibration_curve(y_true: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Compute a reliability diagram (calibration curve).

    Args:
        y_true: True labels.
        proba: Predicted probabilities.
        n_bins: Number of probability bins.

    Returns:
        DataFrame with bin_center, mean_predicted, fraction_positive, count.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (proba >= lo) & (proba < hi) if i < n_bins - 1 else (proba >= lo) & (proba <= hi)
        if mask.sum() == 0:
            continue
        rows.append({
            "bin_center": (lo + hi) / 2,
            "mean_predicted": float(proba[mask].mean()),
            "fraction_positive": float(y_true[mask].mean()),
            "count": int(mask.sum()),
        })
    return pd.DataFrame(rows)


def save_metrics(metrics: dict, path: str | Path) -> None:
    """Save metrics dict as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    logger.info("Saved metrics to %s", path)


def print_metrics_table(all_metrics: dict[str, dict]) -> None:
    """Print a comparison table of all models."""
    print("\n" + "=" * 92)
    print(f"{'Model':<22} {'PR-AUC':>8} {'ROC-AUC':>8} {'Prec':>7} {'Rec':>7} {'F1':>7} {'Brier':>7} {'LiftF1':>7}")
    print("-" * 92)
    for name, m in all_metrics.items():
        lift = m.get("lift_over_persistence_f1")
        lift_s = f"{lift:.3f}" if lift is not None else "   -   "
        print(
            f"{name:<22} {m['pr_auc']:>8.4f} {m['roc_auc']:>8.4f} "
            f"{m['precision']:>7.3f} {m['recall']:>7.3f} {m['f1']:>7.3f} "
            f"{m['brier']:>7.4f} {lift_s:>7}"
        )
    print("=" * 92)


def compute_permutation_importance(
    model, X: pd.DataFrame, y: pd.Series, n_repeats: int = 5, random_state: int = 42
) -> pd.Series:
    """Compute permutation importance (model-agnostic, no leakage)."""
    result = permutation_importance(
        model, X, y, n_repeats=n_repeats, random_state=random_state, n_jobs=-1,
        scoring="average_precision",
    )
    return pd.Series(result.importances_mean, index=X.columns).sort_values(ascending=False)


def degradation_over_time(
    y_true: pd.Series, proba: np.ndarray, threshold: float, n_windows: int = 4
) -> pd.DataFrame:
    """Evaluate PR-AUC and F1 in chronological time windows.

    Splits the test set into n_windows equal-sized chronological chunks
    and reports metrics per window to detect performance drift.
    """
    n = len(y_true)
    size = n // n_windows
    rows = []
    for i in range(n_windows):
        lo = i * size
        hi = (i + 1) * size if i < n_windows - 1 else n
        yt = y_true.iloc[lo:hi].values
        pr = proba[lo:hi]
        pred = (pr >= threshold).astype(int)
        rows.append({
            "window": i,
            "start": str(y_true.index[lo]),
            "end": str(y_true.index[hi - 1]),
            "n": int(hi - lo),
            "positives": int(yt.sum()),
            "pr_auc": float(average_precision_score(yt, pr)),
            "f1": float(f1_score(yt, pred, zero_division=0)),
            "recall": float(recall_score(yt, pred, zero_division=0)),
        })
    return pd.DataFrame(rows)


def error_examples(
    y_true: pd.Series, proba: np.ndarray, threshold: float, n: int = 5
) -> dict[str, pd.DatetimeIndex]:
    """Return timestamps of TP, FP, TN, FN examples for error analysis."""
    pred = (proba >= threshold).astype(int)
    yt = y_true.values
    idx = y_true.index
    tp = idx[(yt == 1) & (pred == 1)][:n]
    fp = idx[(yt == 0) & (pred == 1)][:n]
    tn = idx[(yt == 0) & (pred == 0)][:n]
    fn = idx[(yt == 1) & (pred == 0)][:n]
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn}
