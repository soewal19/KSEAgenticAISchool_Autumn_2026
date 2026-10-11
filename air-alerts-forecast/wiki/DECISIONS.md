# Engineering Decisions

## D-001 — Predict a binary alert-onset event

**Decision:** Estimate whether a new alert begins in `(t, t + H]`, with the default horizon set to 30 minutes.

**Evidence:** [`src/labels.py`](../src/labels.py); [`config.yaml`](../config.yaml).

**Interpretation:** This defines a measurable short-horizon event and supports PR-AUC evaluation for the imbalanced target.

**Trade-off:** It does not forecast alert count, duration, cause, or military decisions.

**Status:** Accepted for this research prototype.

**Confidence:** High that the implementation matches this target definition; predictive usefulness remains limited and must be evaluated separately.

## D-002 — Keep documentation/wiki out of model inputs

**Decision:** Do not use news, Telegram content, RAG retrieval, or wiki text as features in the current model.

**Evidence:** [`src/features.py`](../src/features.py) constructs the current model feature matrix from time-series and calendar inputs. The wiki is maintained under `wiki/` and is not read by the pipeline.

**Interpretation:** Adding timestamped text would require source-time governance and a separate leakage-safe experiment. It is not required for this assignment.

**Status:** Accepted for the current submission scope.

**Confidence:** High.

## D-003 — Purge labels that cross split cutoffs

**Decision:** Purge rows whose forward label window reaches a subsequent partition boundary.

**Evidence:** [`src/labels.py`](../src/labels.py) constructs labels using observations up to `t + H`; [`src/features.py`](../src/features.py) now provides `split_labeled_train_val_test`, and [`src/pipeline.py`](../src/pipeline.py) uses a 30-minute purge at train/validation/test boundaries.

**Interpretation:** Labels near a cutoff can depend on events in the following partition, so the current chronological index check does not guarantee independence of split outcomes.

**Status:** Implemented and covered by unit and leakage-validation checks.

**Confidence:** High.

## D-004 — Preserve regional coverage after the source's level change

**Decision:** Include oblast and raion intervals in parent-oblast series; drop hromada rows and union overlapping intervals.

**Evidence:** Upstream [dataset documentation](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md) describes the shift to mostly raion-level alerts; [`src/preprocessing.py`](../src/preprocessing.py) now retains oblast/raion levels and unions overlapping intervals by parent oblast.

**Interpretation:** The current neighboring-region inputs can become incomplete in the latest period.

**Status:** Implemented; latest upstream data was fetched and the benchmark rerun on 2026-10-12.

**Confidence:** High for the mismatch; medium for the best aggregation policy until overlaps are audited.
