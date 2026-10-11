# Leakage Policy

## Evidence

- The forecast target is a new alert onset during `(t, t + H]`: [`src/labels.py`](../src/labels.py).
- Model inputs at `t` must use data available no later than `t`: [`src/features.py`](../src/features.py).
- The pipeline has chronological split checks and target/lag checks: [`src/validate_no_leakage.py`](../src/validate_no_leakage.py).
- Threshold selection is performed on validation predictions in [`src/models.py`](../src/models.py).

## Rules

1. Features at timestamp `t` may use only source observations published or observed by `t`.
2. Future observations may be used to construct labels, but not to construct features.
3. Train, validation, and test are chronological. Labels must be purged at each boundary so their forward horizon does not cross into the next partition. For a horizon of `H` minutes, exclude rows whose label window reaches or crosses the next split boundary.
4. Fit preprocessing and model parameters on train only. Select thresholds and model variants on validation only. Use test once for final reporting.
5. Any text or media feature must have a verifiable publication timestamp no later than its forecast time. The current project does not use such features.
6. Wiki pages are documentation only. They must never be read as training, validation, test, threshold-selection, or forecast inputs.

## Current check status

**Interpretation:** The validator checks chronological row indices, target/lag alignment, and whether the forward label windows remain inside the training and validation periods.

**Decision:** Purge any training or validation row whose forward target window reaches the next partition.

**Status:** Implemented in `split_labeled_train_val_test`; unit tests and the leakage gate verify the embargo at both cutoffs.

**Confidence:** High; tests assert that every retained training and validation target window ends before its next cutoff.
