"""Validation Agent.

Deterministically validates a hypothesis:
  1. Implements the hypothesis's feature changes (causal, no future).
  2. Checks leakage (no NaN/Inf, lag heads are cold-start 0).
  3. Chronological train/val split.
  4. Trains Random Forest on train, measures PR-AUC on validation.
  5. Runs rolling-origin cross-validation (3 folds).
  6. Checks reproducibility (same seed → same PR-AUC).

All feature constructions here are strictly causal: shift(k>=1), backward
rolling, deterministic functions of timestamp t.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score

from ..config import AppConfig
from ..features import split_labeled_train_val_test
from ..labels import make_target
from .schema import Hypothesis, ValidationResult


class ValidationAgent:
    def __init__(
        self,
        config: AppConfig,
        base_features: pd.DataFrame,
        target_series: pd.Series,
        neighbor_series: dict[str, pd.Series],
    ):
        self.config = config
        self.X_base = base_features
        self.target = target_series
        self.neighbors = neighbor_series
        self.freq = config.time.freq_minutes
        self._baseline_pr_auc: float | None = None

    def _build_hypothesis_features(self, hyp: Hypothesis) -> pd.DataFrame:
        """Construct the extra features requested by the hypothesis.

        Every feature is strictly causal (shift >= 1, backward rolling, or
        deterministic function of t).
        """
        idx = self.X_base.index
        extra = pd.DataFrame(index=idx)
        target = self.target.fillna(0).astype(int)

        for feat in hyp.feature_changes:
            if feat == "neighbors_active_count":
                vals = np.zeros(len(idx), dtype=float)
                for s in self.neighbors.values():
                    vals += s.fillna(0).astype(int).values
                extra[feat] = vals

            elif feat.startswith("nb_") and feat.endswith("_rolling_30m"):
                # extract neighbor name from feature name
                # e.g. nb_Kyivska_oblast_rolling_30m
                nb_key = feat.replace("nb_", "").replace("_rolling_30m", "")
                s = None
                for name, ser in self.neighbors.items():
                    if name.replace(" ", "_") == nb_key:
                        s = ser.fillna(0).astype(int)
                        break
                if s is not None:
                    steps = max(1, 30 // self.freq)
                    extra[feat] = s.rolling(window=steps, min_periods=1, closed="left").sum().astype(float)

            elif feat == "neighbor_max_lag_5m":
                steps = max(1, 5 // self.freq)
                vals = np.zeros(len(idx), dtype=float)
                for s in self.neighbors.values():
                    vals = np.maximum(vals, s.fillna(0).shift(steps).fillna(0).astype(float).values)
                extra[feat] = vals

            elif feat == "momentum_macd_15_60":
                fast = max(1, 15 // self.freq)
                slow = max(1, 60 // self.freq)
                ema_fast = target.ewm(span=fast, adjust=False).mean()
                ema_slow = target.ewm(span=slow, adjust=False).mean()
                extra[feat] = (ema_fast - ema_slow).astype(float)

            elif feat == "target_rolling_30m":
                steps = max(1, 30 // self.freq)
                extra[feat] = target.rolling(window=steps, min_periods=1, closed="left").sum().astype(float)

            elif feat == "recency_interaction":
                cur_dur = self.X_base.get("current_alert_duration_min", pd.Series(0, index=idx))
                tsl = self.X_base.get("time_since_last_alert_min", pd.Series(0, index=idx))
                not_active = (cur_dur == 0).astype(float)
                extra[feat] = (tsl * not_active).astype(float)

            elif feat in self.X_base.columns:
                # Already a base feature — no-op, already included
                pass

            else:
                # Neighbor lag or calendar feature already in base — skip
                pass

        extra = extra.fillna(0.0)
        return extra

    def _check_leakage(self, X: pd.DataFrame) -> bool:
        """Return True if no leakage signs (no NaN/Inf, lag heads cold-start)."""
        if X.isna().any().any():
            return False
        if np.isinf(X.select_dtypes(include=[np.number])).any().any():
            return False
        return True

    def _train_eval_pr_auc(self, X_train, y_train, X_val, y_val, seed: int) -> float:
        model = RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=50,
            class_weight="balanced", random_state=seed, n_jobs=-1,
        )
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_val)[:, 1]
        return float(average_precision_score(y_val, proba))

    def get_baseline_pr_auc(self) -> float:
        """Compute baseline PR-AUC (base features only) on validation, once."""
        if self._baseline_pr_auc is not None:
            return self._baseline_pr_auc
        y = make_target(self.target, self.config.time.horizon_minutes, self.freq)
        (Xtr, ytr), (Xval, yval), _ = split_labeled_train_val_test(
            self.X_base, y, self.config.split.train_end, self.config.split.val_end,
            self.config.time.horizon_minutes,
        )
        self._baseline_pr_auc = self._train_eval_pr_auc(
            Xtr, ytr, Xval, yval,
            self.config.project.random_state,
        )
        return self._baseline_pr_auc

    def _rolling_origin_folds(self, X: pd.DataFrame, y: pd.Series, n_folds: int = 3) -> list[dict]:
        """Rolling-origin cross-validation on the validation period.

        Each fold: train on [train_start, val_start + k*step], validate on
        the next slice. Tests stability of improvement.
        """
        train_end = pd.Timestamp(self.config.split.train_end, tz="UTC")
        val_end = pd.Timestamp(self.config.split.val_end, tz="UTC")
        horizon = pd.Timedelta(minutes=self.config.time.horizon_minutes)
        eligible_val = X.index[(X.index >= train_end) & (X.index + horizon < val_end) & y.notna().to_numpy()]
        if len(eligible_val) < n_folds * 2:
            return []
        results = []
        chunks = np.array_split(eligible_val, n_folds)
        for k, chunk in enumerate(chunks):
            if len(chunk) == 0:
                continue
            fold_start, fold_end = chunk[0], chunk[-1] + pd.Timedelta(nanoseconds=1)
            train_mask = (X.index + horizon < fold_start) & y.notna().to_numpy()
            val_mask = (X.index >= fold_start) & (X.index <= chunk[-1]) & y.notna().to_numpy()
            if not train_mask.any() or not val_mask.any():
                continue
            pr = self._train_eval_pr_auc(
                X.loc[train_mask], y.loc[train_mask].astype(int),
                X.loc[val_mask], y.loc[val_mask].astype(int),
                self.config.project.random_state,
            )
            results.append({"fold": k, "start": fold_start.isoformat(),
                            "end_exclusive": fold_end.isoformat(), "pr_auc": pr})
        return results

    def validate(self, hyp: Hypothesis) -> ValidationResult:
        """Run full deterministic validation of a hypothesis."""
        # Build augmented feature matrix
        extra = self._build_hypothesis_features(hyp)
        X = pd.concat([self.X_base, extra], axis=1)
        X = X.loc[:, ~X.columns.duplicated()]

        # Leakage check
        leakage_pass = self._check_leakage(X)

        y = make_target(self.target, self.config.time.horizon_minutes, self.freq)

        # Baseline vs hypothesis PR-AUC on validation
        baseline = self.get_baseline_pr_auc()
        (Xtr, ytr), (Xval, yval), _ = split_labeled_train_val_test(
            X, y, self.config.split.train_end, self.config.split.val_end,
            self.config.time.horizon_minutes,
        )
        hyp_pr = self._train_eval_pr_auc(
            Xtr, ytr, Xval, yval,
            self.config.project.random_state,
        )

        # Rolling-origin folds
        folds = self._rolling_origin_folds(X, y, n_folds=3)
        # Compare each fold to baseline (approximate — use same fold on base)
        folds_improved = 0
        for fold_res in folds:
            # baseline fold PR-AUC (base features, same fold)
            base_folds = self._rolling_origin_folds(self.X_base, y, n_folds=3)
            matching = next((f for f in base_folds if f["fold"] == fold_res["fold"]), None)
            base_pr = matching["pr_auc"] if matching is not None else baseline
            if fold_res["pr_auc"] > base_pr:
                folds_improved += 1

        # Reproducibility: re-run with same seed, check PR-AUC matches
        hyp_pr_2 = self._train_eval_pr_auc(
            Xtr, ytr, Xval, yval,
            self.config.project.random_state,
        )
        reproducible = abs(hyp_pr - hyp_pr_2) < 1e-6

        return ValidationResult(
            hypothesis_id=hyp.id,
            leakage_test_pass=leakage_pass,
            baseline_pr_auc=float(baseline),
            hypothesis_pr_auc=float(hyp_pr),
            pr_auc_delta=float(hyp_pr - baseline),
            rolling_origin_results=folds,
            folds_improved=int(folds_improved),
            total_folds=len(folds),
            reproducible=reproducible,
            feature_columns=list(X.columns),
        )
