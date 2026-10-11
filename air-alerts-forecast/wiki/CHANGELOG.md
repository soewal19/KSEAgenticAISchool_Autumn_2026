# Wiki Changelog

## 2026-10-12

- Added a 30-minute purge for forward labels across train/validation/test cutoffs, with explicit leakage checks.
- Aggregated oblast and raion intervals by parent oblast, unioning overlaps and dropping nested hromada rows.
- Refreshed the upstream source snapshot; it returned the same data through 2026-09-07 05:28:22 UTC. Recomputed the full holdout metrics and updated result documentation.
- Isolated smoke artifacts under `outputs/smoke/` and replaced the reconstructed AI process note with the retained conversation export.

## 2026-10-11

- Created the Markdown knowledge base and linked its index from the project README.
- Recorded a source-backed note on the upstream move toward raion-level reporting and the current oblast-only cleaner.
- Marked neighbor-feature utility as pending rather than accepted because the current benchmark has known temporal and coverage gaps.
- Recorded the current metric snapshot with its split-boundary and artifact-consistency caveats.
- Added a formal policy stating that wiki content is not a forecasting input and that forward labels must be purged at split boundaries.
