"""Model definitions and training.

Models implemented:
1. Persistence baseline: if alert active at t, predict continuation;
   otherwise predict no new alert. Probability is the train base rate.
2. Seasonal baseline: probability of a new alert start by (hour, dayofweek),
   estimated ONLY on train.
3. Logistic Regression.
4. Random Forest.
5. LightGBM.

All scalers/encoders/thresholds are fit on train only. Chronological
split is enforced by the caller (features.split_train_val_test).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .config import AppConfig
from .logger import get_logger

logger = get_logger("models")


class PersistenceBaseline:
    """Persistence baseline.

    Predict y=1 (alert will start/continue) iff an alert is active at t.
    Probability output = train base rate of target when active, else
    1 - train base rate when inactive (calibrated-ish).
    """

    def __init__(self) -> None:
        self.base_rate_: float = 0.5

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "PersistenceBaseline":
        self.base_rate_ = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        active = X["target_lag_5m"].fillna(0).values if "target_lag_5m" in X else np.zeros(len(X))
        p1 = np.where(active >= 0.5, self.base_rate_ + 0.4, self.base_rate_ - 0.1)
        p1 = np.clip(p1, 1e-6, 1 - 1e-6)
        return np.column_stack([1 - p1, p1])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class SeasonalBaseline:
    """Seasonal baseline: P(start | hour, dayofweek) estimated on train."""

    def __init__(self, smooth: float = 1.0) -> None:
        self.smooth = smooth
        self.table_: pd.DataFrame | None = None
        self.global_rate_: float = 0.5

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "SeasonalBaseline":
        self.global_rate_ = float(y.mean())
        tmp = pd.DataFrame({"hour": X["hour"].astype(int), "dow": X["dayofweek"].astype(int), "y": y})
        grp = tmp.groupby(["hour", "dow"])["y"]
        cnt = grp.count()
        s = grp.sum()
        smoothed = (s + self.smooth * self.global_rate_) / (cnt + self.smooth)
        self.table_ = smoothed.reset_index().rename(columns={"y": "p"})
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        tmp = pd.DataFrame({"hour": X["hour"].astype(int), "dow": X["dayofweek"].astype(int)})
        merged = tmp.merge(self.table_, on=["hour", "dow"], how="left")["p"].fillna(self.global_rate_).values
        p1 = np.clip(merged, 1e-6, 1 - 1e-6)
        return np.column_stack([1 - p1, p1])

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def build_sklearn_model(name: str, random_state: int, y_train: pd.Series | None = None) -> Any:
    """Instantiate a scikit-learn / lightgbm model by name."""
    if name == "logistic_regression":
        return LogisticRegression(
            max_iter=1000, random_state=random_state, class_weight="balanced", n_jobs=-1
        )
    if name == "random_forest":
        return RandomForestClassifier(
            n_estimators=300, max_depth=None, min_samples_leaf=50,
            class_weight="balanced", random_state=random_state, n_jobs=-1,
        )
    if name == "lightgbm":
        from lightgbm import LGBMClassifier
        if y_train is not None:
            pos = int(y_train.sum())
            neg = int(len(y_train) - pos)
            spw = neg / max(1, pos)
        else:
            spw = 1.0
        return LGBMClassifier(
            n_estimators=500, learning_rate=0.05, num_leaves=63,
            min_child_samples=100, subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=spw,
            random_state=random_state, n_jobs=-1, verbose=-1,
        )
    raise ValueError(f"Unknown model: {name}")


def select_threshold(
    y_val: np.ndarray,
    proba_val: np.ndarray,
    metric: str = "f1",
    min_recall: float = 0.70,
) -> tuple[float, dict]:
    """Select a decision threshold on validation only.

    Strategy:
      - if metric == 'f1': pick threshold maximizing F1.
      - else: pick the lowest threshold achieving recall >= min_recall.

    Args:
        y_val: Validation labels.
        proba_val: Validation predicted probabilities (class 1).
        metric: 'f1' or 'recall'.
        min_recall: Minimum recall target for recall mode.

    Returns:
        (threshold, metrics_at_threshold).
    """
    from sklearn.metrics import f1_score, precision_score, recall_score
    thresholds = np.unique(np.quantile(proba_val, np.linspace(0, 1, 201)))
    best_t, best_score, best_metrics = 0.5, -1.0, {}
    for t in thresholds:
        pred = (proba_val >= t).astype(int)
        r = recall_score(y_val, pred, zero_division=0)
        p = precision_score(y_val, pred, zero_division=0)
        f = f1_score(y_val, pred, zero_division=0)
        if metric == "f1":
            if f > best_score:
                best_score, best_t = f, t
                best_metrics = {"threshold": t, "precision": p, "recall": r, "f1": f}
        else:
            if r >= min_recall and t > best_t:
                best_t = t
                best_metrics = {"threshold": t, "precision": p, "recall": r, "f1": f}
    if not best_metrics:
        best_metrics = {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    return float(best_t), best_metrics


def fit_model(
    name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    config: AppConfig,
) -> tuple[Any, StandardScaler | None, float, dict]:
    """Fit a model, fit scaler on train, select threshold on val.

    Returns:
        (fitted_model, scaler_or_None, threshold, val_metrics).
    """
    rs = config.project.random_state
    scaler = None
    X_predict = X_val

    if name == "persistence":
        model = PersistenceBaseline().fit(X_train, y_train)
    elif name == "seasonal":
        model = SeasonalBaseline().fit(X_train, y_train)
    else:
        scaler = StandardScaler()
        Xtr = pd.DataFrame(
            scaler.fit_transform(X_train), columns=X_train.columns, index=X_train.index
        )
        X_predict = pd.DataFrame(
            scaler.transform(X_val), columns=X_val.columns, index=X_val.index
        )
        model = build_sklearn_model(name, rs, y_train)
        model.fit(Xtr, y_train)

    proba_val = model.predict_proba(X_predict)[:, 1]
    threshold, val_metrics = select_threshold(
        y_val.values, proba_val, config.threshold.metric, config.threshold.min_recall
    )
    logger.info(
        "Model %s fit. val threshold=%.4f val_f1=%.4f",
        name, threshold, val_metrics.get("f1", 0.0),
    )
    return model, scaler, threshold, val_metrics
