# Model Card

## Model overview

The pipeline compares persistence and seasonal baselines with logistic regression, random forest, and LightGBM. The current full-data metrics snapshot identifies logistic regression as the highest-PR-AUC model for the configured 30-minute horizon.

## Intended use

Retrospective research and educational evaluation of short-horizon alert-onset prediction. Not intended for real-time public warning or safety decisions.

## Evaluation data

- Target region: Kyiv City.
- Forecast horizon: 30 minutes.
- Grid frequency: five minutes.
- Train: timestamps before 2023-12-31 00:00 UTC.
- Validation: 2023-12-31 00:00 through 2024-06-29 23:55 UTC.
- Test: 2024-06-30 00:00 through 2026-09-07 05:05 UTC.
- Test rows: 230,174; positive rows: 7,543; observed positive rate: 3.28%.
- A 30-minute label embargo removes training/validation rows whose target windows would cross the following split boundary.
- Thresholds are chosen on validation only. The test period is not used for threshold selection.

## Full-data holdout metrics

Metrics are from outputs/metrics/test_metrics.json. Values are rounded.

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| Persistence | 0.032 | 0.475 | 0.033 | 1.000 | 0.064 | 0.047 |
| Seasonal | 0.035 | 0.517 | 0.034 | 0.123 | 0.053 | 0.032 |
| Logistic regression | **0.103** | **0.722** | **0.125** | 0.417 | **0.193** | 0.181 |
| Random forest | 0.089 | 0.709 | 0.073 | **0.547** | 0.128 | 0.182 |
| LightGBM | 0.053 | 0.570 | 0.075 | 0.141 | 0.098 | 0.051 |

Logistic regression's test PR-AUC is about 3.20 times the persistence baseline's PR-AUC. Its precision is 12.5%, with a 9.9% false-positive rate at the validation-selected threshold. This retrospective result does not establish operational readiness.

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
