# Research Notes

## R-001 — Air-alert activity has spatial and temporal structure

**Evidence**

- The arXiv abstract for [Pavlyshenko & Pavlyshenko, *Predictive Analytics of Air Alerts in the Russian-Ukrainian War*](https://arxiv.org/abs/2411.14625) reports cross-region correlations, geospatial patterns, neighboring-region dependence, seasonality, and changes in alert patterns over time.
- The current pipeline includes calendar features and past-only lags for Kyiv City and selected neighboring regions: [`src/features.py`](../src/features.py), configured in [`config.yaml`](../config.yaml).
- The repository's exploratory cross-region plot is [`outputs/figures/cross_region_correlation.png`](../outputs/figures/cross_region_correlation.png).

**Interpretation**

The paper motivates testing spatial and calendar features; it does not establish that those features improve this project's 30-minute forecast. Correlation is not causal evidence. The paper's results do not substitute for this project's leakage-safe validation.

**Decision**

Retain these feature families as hypotheses, not as assumed sources of predictive value. Evaluate them on time-ordered data after fixing split-boundary label overlap and the source administrative-level change.

**Confidence**

Medium that the source supports these as research directions; low that the existing experiment establishes their value for the current target.

## R-002 — Dataset coverage and administrative levels change

**Evidence**

- The [upstream dataset documentation](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset/blob/main/datasets/README.md) says the datasets are updated daily and notes that since December 2025 alerts are mostly recorded at raion (district) level.
- The local `data/raw/official_data_en.csv` snapshot inspected on 2026-10-11 spans 2022-03-15 through 2026-09-07. For the configured neighboring oblasts after 2025-12-01, the local file has rows at `raion` level; [`src/preprocessing.py`](../src/preprocessing.py) currently keeps only `level == "oblast"`.
- The configured loader reuses a non-empty local file instead of checking the upstream version or freshness: [`src/data_loader.py`](../src/data_loader.py).

**Interpretation**

The current cleaning path can discard most neighboring-region observations after the administrative reporting change. The local snapshot date alone does not prove that it is the latest data available at submission time.

**Decision**

Before treating a refreshed benchmark as representative, implement and validate a region-level aggregation policy for raion rows (including overlap handling), refresh the source snapshot, and record the exact data cutoff and digest.

**Confidence**

High for the behavior of the checked-in cleaner and local CSV snapshot; the upstream dataset may have changed since the local copy was obtained.
