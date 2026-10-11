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

**Interpretation:** The existing validator confirms chronological row indices and checks target/lag alignment, but it does not test whether forward-looking labels cross `train_end` or `val_end`.

**Decision:** The current pipeline does not yet satisfy Rule 3. Add boundary-purge checks and tests before treating current holdout metrics as leakage-safe.

**Confidence:** High; this follows directly from the target horizon and timestamp-only split implementation.
