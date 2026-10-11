# Hypotheses

## H-001 — Neighbor-region history improves short-horizon Kyiv City forecasts

**Claim:** Past alert activity in Kyivska, Chernihivska, and Sumska oblasts may add useful information when estimating whether a new Kyiv City alert begins within 30 minutes.

**Rationale:** The cited air-alert study reports regional dependence, and the exploratory correlation figure shows co-variation in the current snapshot. Neither source proves a causal or out-of-sample improvement.

**Implementation:** The current base feature builder uses causal lags for each configured neighboring series (for example, `nb_Kyivska_oblast_lag_5m`); see [`src/features.py`](../src/features.py) and [`config.yaml`](../config.yaml). These columns must be built from region-level series that remain valid after the source's shift to raion reporting.

**Acceptance criteria:**

- No-leakage tests pass, including a forecast-horizon embargo at train/validation/test boundaries.
- Neighbor features improve PR-AUC over a local-history baseline on validation data.
- The improvement is stable across correctly implemented rolling-origin validation folds.
- The regional aggregation is consistent across the source's administrative-level change.

**Status:** Pending. The main reported benchmark uses a single chronological holdout; the separate hypothesis-validation module is not evidence that this hypothesis has passed the above criteria.

**Evidence:** [`outputs/figures/cross_region_correlation.png`](../outputs/figures/cross_region_correlation.png); feature implementation in [`src/features.py`](../src/features.py); related study in [arXiv:2411.14625](https://arxiv.org/abs/2411.14625). A valid comparative experiment is not yet recorded.

**Interpretation:** Spatial lags are worth testing but should not be described as validated improvements until the evaluation gaps are resolved.

**Decision:** Keep the hypothesis open; do not claim acceptance from the current full-run metric snapshot.

**Confidence:** Low pending leakage-safe, level-consistent comparative results.
