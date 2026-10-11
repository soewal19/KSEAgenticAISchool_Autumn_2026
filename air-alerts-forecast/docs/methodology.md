# Methodology

## Problem formulation

This project estimates a short-horizon conditional probability of a new alert onset. It does not estimate the number of alerts or claim to predict military decisions.

For region r, timestamp t, and forecast horizon H:

~~~text
P(y[r,t,H] = 1 | X available at or before t)
~~~

The binary target is 1 if a new alert starts in the interval (t, t + H], 0 otherwise. The current grid cell is excluded. The final H minutes are unlabeled because their future is not observed.

## Why binary onset classification

Alert onsets are irregular and affected by external factors that are not observed in this dataset. A binary onset target makes the event being evaluated explicit: whether a new alert begins during the chosen horizon. It is not a claim that alerts can be controlled or reliably anticipated.

## Data preparation

The source contains alert intervals across oblast, raion, and hromada administrative levels. Regional analysis keeps oblast and raion rows, assigns them to their parent oblast, and drops hromada rows to avoid counting nested representations repeatedly. Exact duplicate intervals within a level are removed; overlapping intervals are unioned into a binary regional activity series. Timestamps are parsed as UTC and invalid intervals are removed. A five-minute grid cell is active if any retained interval overlaps it.

## Causal feature policy

Every model input at time t must be available no later than t.

Allowed feature families:

- Target-region and neighboring-region activity lags, each shifted by at least one grid step.
- Alert-onset counts over past windows. The onset series is shifted before rolling aggregation so the window ends before t.
- Current alert duration and time since the previous alert, computed from activity observed through t.
- Calendar variables derived deterministically from t, including hour, weekday, month, and cyclic encodings.

The pipeline does not use negative shifts, future observations, validation/test-fitted scalers, test-selected thresholds, or text published after the forecast timestamp. The current implementation does not include EMA, MACD, or external media features.

## Spatial features

Neighboring regions may show related alert activity, so the model tests lagged activity from Kyivska, Chernihivska, and Sumska oblasts alongside Kyiv City history. This is a hypothesis, not an assumption: the relevance of spatial features must be judged by out-of-sample metrics. Correlation in the exploratory plot alone does not establish predictive value or causality.

![Correlation between regional alert-activity series](../outputs/figures/cross_region_correlation.png)

## Temporal validation

Random splitting is inappropriate because it allows observations from later periods to influence evaluation of earlier observations. The current configuration uses a single chronological split:

| Partition | UTC interval |
|---|---|
| Train | Before 2023-12-31 00:00 |
| Validation | 2023-12-31 00:00 through 2024-06-29 23:55 |
| Test | From 2024-06-30 00:00 through the final observed grid cell |

The cutoffs are half-open: train ends at train_end, validation ends at val_end, and test begins at val_end. A label is retained in train or validation only if its full forward horizon ends strictly before that partition's cutoff; this purges the final 30 minutes before each boundary. Test labels are retained only when observed. Scalers are fit on training data. Thresholds are selected on validation data and then frozen for test evaluation.

The test period is also split into four chronological chunks to inspect metric degradation. This is a descriptive breakdown of one fixed test holdout, not rolling-origin backtesting. The separate hypothesis-validation subsystem evaluates candidate feature changes on three expanding rolling-origin folds inside validation; it is not the primary benchmark reported here.

## Metrics

New-alert onset rows are uncommon, so accuracy can be high for a model that predicts no events. PR-AUC (Average Precision) is the primary ranking metric. ROC-AUC, precision, recall, F1 at the validation-selected threshold, Brier score, calibration, and the confusion matrix provide complementary views.

The threshold represents a trade-off between missed onsets and false positives. It is chosen on validation only. A high recall or PR-AUC does not by itself mean the model is operationally useful.

## Figures and what they answer

The data stage writes PNG figures to outputs/figures. The figures below have distinct analytical purposes:

| Figure | Question it answers |
|---|---|
| monthly_activity_Kyiv_City.png | Does the fraction of active five-minute cells vary across months? |
| hourly_activity_Kyiv_City.png | Is alert activity distributed differently by hour of day? |
| cross_region_correlation.png | How strongly do regional activity series co-vary in this dataset? |
| alert_durations_by_region.png | How do median alert durations compare across regions? |
| calibration_curves.png | Do predicted probabilities align with observed positive frequencies? |
| permutation_importance.png | Which features most affect the selected model's score under permutation? |

Permutation importance is model-agnostic but can be noisy when predictors are correlated. It describes this fitted model and dataset, not a causal effect. The code does not currently generate a rolling-origin PR-AUC chart or a confusion-matrix image; numerical metrics and test predictions are saved separately.

## Limitations and responsible use

- The dataset contains historical alert intervals, not the full information available to civil-protection authorities.
- Alert patterns are non-stationary and can change abruptly.
- The observed association between historical features and alert onsets is not causal.
- The class is imbalanced, and the best reported model has low precision and many false positives.
- This retrospective project is not a public-warning service and must not guide safety decisions.

Follow official Ukrainian alert channels and civil-protection guidance.
