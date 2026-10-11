# Results

## Current checked-in full-run snapshot

**Evidence:** [`outputs/metrics/test_metrics.json`](../outputs/metrics/test_metrics.json), generated from the local dataset snapshot. The test predictions span 2024-06-30 00:00 UTC through 2026-09-05 23:10 UTC (`outputs/predictions/test_predictions.parquet`, when available locally). The test set contains 229,815 rows with a 3.28% positive rate.

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| Persistence | 0.0321 | 0.4747 | 0.0328 | 1.0000 | 0.0635 | 0.0472 |
| Seasonal | 0.0345 | 0.5170 | 0.0340 | 0.1232 | 0.0532 | 0.0319 |
| Logistic regression | 0.0773 | 0.6267 | 0.0328 | 1.0000 | 0.0635 | 0.1183 |
| Random forest | 0.0793 | 0.6279 | 0.0385 | 0.7865 | 0.0733 | 0.1172 |
| LightGBM | 0.0426 | 0.5392 | 0.0427 | 0.1598 | 0.0674 | 0.0550 |

## Interpretation

The random forest has the highest PR-AUC in this snapshot, but its precision is about 3.8% and its false-positive rate is about 66.7% at the stored validation-selected threshold. The test prevalence is low, and thresholded predictions are not suitable for operational use.

The snapshot is not currently a clean final benchmark: split-boundary label overlap has not been purged, and the regional preprocessing drops most post-December-2025 raion-level records for neighboring oblasts. Recompute results after those issues and data freshness are addressed.

## Artifact consistency note

[`outputs/metrics/degradation_over_time.csv`](../outputs/metrics/degradation_over_time.csv) currently contains smoke-period dates in January 2024, while `test_metrics.json` describes the full holdout through September 2026. The smoke configuration shares the metrics directory and writes the same degradation filename. Do not interpret that CSV as the full-run degradation report until output paths are separated and the full evaluation is rerun.

## Decision

Treat these values as a historical artifact snapshot only. Do not choose or tune anything on the test period, and do not report the current metrics as leakage-safe final performance.

## Confidence

High that the listed numbers match the checked-in JSON; low that they represent an unbiased final estimate because of the documented split and data-level issues.
