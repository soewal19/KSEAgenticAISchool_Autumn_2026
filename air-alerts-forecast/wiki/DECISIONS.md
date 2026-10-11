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

**Decision:** The current split policy needs an embargo of at least the forecast horizon at train/validation boundaries before its metrics can be treated as leakage-safe.

**Evidence:** [`src/labels.py`](../src/labels.py) constructs labels using observations up to `t + H`; [`src/features.py`](../src/features.py) currently partitions rows by timestamp alone; [`src/pipeline.py`](../src/pipeline.py) applies those row splits to features and labels.

**Interpretation:** Labels near a cutoff can depend on events in the following partition, so the current chronological index check does not guarantee independence of split outcomes.

**Status:** Required correction, not yet implemented.

**Confidence:** High.

## D-004 — Preserve regional coverage after the source's level change

**Decision:** Do not silently discard post-2025 raion observations when constructing oblast-level regional series.

**Evidence:** Upstream [dataset documentation](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md) describes the shift to mostly raion-level alerts; [`src/preprocessing.py`](../src/preprocessing.py) currently filters to oblast-level records.

**Interpretation:** The current neighboring-region inputs can become incomplete in the latest period.

**Status:** Aggregation policy and refreshed evaluation are still required.

**Confidence:** High for the mismatch; medium for the best aggregation policy until overlaps are audited.
