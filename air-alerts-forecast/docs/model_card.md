# Model Card

## Model overview

The pipeline compares persistence and seasonal baselines with logistic regression, random forest, and LightGBM. The current full-data metrics snapshot identifies the random forest as the highest-PR-AUC model for the configured 30-minute horizon.

## Intended use

Retrospective research and educational evaluation of short-horizon alert-onset prediction. Not intended for real-time public warning or safety decisions.

## Evaluation data

- Target region: Kyiv City.
- Forecast horizon: 30 minutes.
- Grid frequency: five minutes.
- Train: timestamps before 2023-12-31 00:00 UTC.
- Validation: 2023-12-31 00:00 through 2024-06-29 23:55 UTC.
- Test: 2024-06-30 00:00 through 2026-09-05 23:10 UTC in the saved snapshot.
- Test rows: 229,815; positive rows: 7,542; observed positive rate: 3.28%.
- Thresholds are chosen on validation only. The test period is not used for threshold selection.

## Full-data holdout metrics

Metrics are from outputs/metrics/test_metrics.json. Values are rounded.

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| Persistence | 0.032 | 0.475 | 0.033 | 1.000 | 0.064 | 0.047 |
| Seasonal | 0.035 | 0.517 | 0.034 | 0.123 | 0.053 | 0.032 |
| Logistic regression | 0.077 | 0.627 | 0.033 | 1.000 | 0.064 | 0.118 |
| Random forest | **0.079** | **0.628** | 0.038 | 0.787 | **0.073** | 0.117 |
| LightGBM | 0.043 | 0.539 | 0.043 | 0.160 | 0.067 | 0.055 |

The random forest's test PR-AUC is about 2.47 times the persistence baseline's PR-AUC. However, its precision is 3.8%, and its false-positive rate at the chosen threshold is about 66.7%. The lift should not be interpreted as operational readiness.

## Inputs

Inputs are past-only target and neighboring-region activity lags, rolling past onset counts, current alert duration, time since the previous alert, and calendar features. No post-forecast observations or post-timestamp text is used.

## Limitations

- Alert behavior is non-stationary and may change beyond the historical test period.
- Unobserved external factors are not represented.
- Low precision implies many false positives.
- Metrics describe one chronological holdout; the four test-period chunks are not rolling-origin folds.
- Permutation importance is descriptive, can be unstable with correlated features, and does not establish causality.

## Safety statement

This model is not an early-warning system. Follow official Ukrainian air-alert channels and civil-protection instructions.
