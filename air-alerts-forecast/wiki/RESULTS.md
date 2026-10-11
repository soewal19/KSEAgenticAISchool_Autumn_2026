# Results

## Leakage-safe full-run snapshot (2026-10-12)

**Data:** 299,275 source rows, fetched from the configured upstream URL. Latest alert start: 2026-09-07 05:28:22 UTC. SHA-256: `b396f87696243069eec0219880e87dcd642b20beb0a7bae0d0e1f61e1ed20ec4`.

**Evaluation:** one chronological holdout with a 30-minute purge before the train/validation and validation/test cutoffs. The test set has 230,174 rows and 7,543 positives (3.28%). The four degradation windows describe chunks within that one test holdout; they are not rolling-origin backtesting.

| Model | PR-AUC | ROC-AUC | Precision | Recall | F1 | Brier |
|---|---:|---:|---:|---:|---:|---:|
| Persistence | 0.0321 | 0.4747 | 0.0328 | 1.0000 | 0.0635 | 0.0471 |
| Seasonal | 0.0345 | 0.5172 | 0.0340 | 0.1232 | 0.0532 | 0.0318 |
| Logistic regression | **0.1029** | **0.7225** | **0.1253** | 0.4175 | **0.1927** | 0.1805 |
| Random forest | 0.0890 | 0.7085 | 0.0728 | **0.5467** | 0.1285 | 0.1822 |
| LightGBM | 0.0528 | 0.5696 | 0.0746 | 0.1412 | 0.0976 | 0.0508 |

Logistic regression has the highest PR-AUC, about 3.20 times persistence. Its validation-selected threshold yields 12.5% precision and a 9.9% false-positive rate. This is still a retrospective benchmark with substantial false positives, not an operational warning system.

## Artifact consistency

The full run writes `test_metrics.json` and `degradation_over_time.csv` under `outputs/metrics/`. Smoke configuration now writes to `outputs/smoke/metrics/`; smoke runs do not overwrite the full-run degradation table.

## Decision

Treat these values as a leakage-controlled retrospective holdout, not proof of future performance. The dataset is non-stationary and this remains a single holdout evaluation.
