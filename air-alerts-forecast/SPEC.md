# Behavioral Specification — Air-Alert Forecasting

This document defines the target, time splits, causal-feature rules, threshold selection, and pipeline invariants. Update it when implementation or tests change.

## 1. Target

The task is binary prediction of a new alert onset in the selected region during the half-open interval (t, t + H]. H is configurable and defaults to 30 minutes.

~~~text
y_t = 1 if a new alert starts in (t, t + H]
y_t = 0 otherwise
y_t = NaN when the full future horizon is not observed
~~~

- The current grid cell t is excluded.
- A new onset is a 0-to-1 transition in the binary alert-activity series, not continuation of an alert already active at t.
- The grid frequency defaults to five minutes.
- Rows without a fully observed future horizon are excluded from model fitting and evaluation.

Implementation: [src/labels.py](src/labels.py), function make_target.

Tests: test_make_target_is_forward_looking and test_make_target_excludes_current_cell.

## 2. Chronological split

The configured cutoffs are exclusive:

~~~text
train: [data_start, train_end)
validation: [train_end, val_end)
test: [val_end, data_end]
~~~

Current configuration: train_end is 2023-12-31 and val_end is 2024-06-30. Therefore the test period begins at 2024-06-30 00:00 UTC.

- Splits use a UTC DatetimeIndex and do not shuffle rows.
- Splits must not overlap and must remain ordered in time.
- The threshold is selected on validation only.
- Final reported metrics are computed on the held-out test period.

Implementation: [src/features.py](src/features.py), function split_train_val_test.

## 3. Causal-feature policy

Every feature at time t must be computable from data available at or before t.

| Feature operation | Rule | Implementation |
|---|---|---|
| Target-region lag | Shift by k steps where k is at least 1 | add_lag_features |
| Neighbor-region lag | Shift by k steps where k is at least 1 | add_lag_features |
| Rolling onset count | Shift the onset series by one step before rolling; use a past-only window | add_rolling_alert_counts |
| Calendar values | Deterministic functions of t | add_calendar_features |
| Current state | Derive duration and recency from observed values through t | add_current_alert_duration, add_time_since_last_alert |

Forbidden operations include negative shifts, windows that use future observations, fitting scalers or other learned transformations on validation or test, selecting thresholds on test, or using external content published after t.

The current model does not use EMA, MACD, or external text features.

## 4. Threshold selection

The threshold is selected separately for each model using validation predictions only.

| Configuration | Selection rule |
|---|---|
| metric: f1 | Choose the candidate threshold with the highest validation F1 |
| metric: recall | Choose the largest candidate threshold that reaches min_recall |

The default minimum recall is 0.70. Candidates are drawn from 201 quantiles of validation probabilities. Test probabilities are evaluated with the chosen validation threshold unchanged.

Implementation: [src/models.py](src/models.py), function select_threshold.

## 5. Metrics and evaluation

PR-AUC (Average Precision) is the primary ranking metric because the positive class is uncommon. Secondary metrics include ROC-AUC, precision, recall, F1, Brier score, calibration, confusion matrix, and comparison with the persistence baseline.

The current project uses one chronological train/validation/test holdout. It also divides the test period into four ordered chunks to inspect degradation. That analysis is not rolling-origin backtesting.

## 6. Pipeline invariants

1. All lag features use at least one past step.
2. Rolling onset features exclude information after the forecast timestamp.
3. The target is forward-looking; features are not.
4. Splits are ordered and disjoint.
5. Thresholds are selected on validation only.
6. Scalers are fitted on training data only.
7. Each full run writes a JSON run log with a run ID, configuration hash, feature names, and metrics.
