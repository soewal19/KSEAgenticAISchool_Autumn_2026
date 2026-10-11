# Project Wiki

This lightweight, AI-assisted Markdown wiki preserves research and engineering knowledge for the air-alert forecasting project. It is a documentation and project-memory layer only. Wiki pages are never read by the forecasting pipeline and are not model inputs.

## Pages

- [Research](RESEARCH.md) — source notes and how they inform the project.
- [Hypotheses](HYPOTHESES.md) — testable feature hypotheses and their current status.
- [Decisions](DECISIONS.md) — accepted choices and unresolved engineering decisions.
- [Results](RESULTS.md) — the checked-in metric snapshot and caveats.
- [Leakage policy](LEAKAGE_POLICY.md) — temporal rules, checks, and known gaps.
- [Changelog](CHANGELOG.md) — changes to this wiki.

## Update protocol

When adding a dataset observation, source, hypothesis, or experiment, update the relevant page and this index if the page list changes. Cite the source file, URL, test, or run artifact. Separate evidence from interpretation and decision. Never edit raw data, model configuration, code, or metric artifacts as part of a wiki update. Do not use a wiki page to select a test threshold or supply model features.

## Evidence / interpretation / decision / confidence

**Evidence:** The repository contains the project code, documentation, tests, and metric artifacts linked from the wiki pages.  
**Interpretation:** A compact set of linked Markdown notes is sufficient for this project's current research scope.  
**Decision:** Keep this wiki in Markdown; do not add RAG, embeddings, a vector database, or external storage.  
**Confidence:** High for the repository policy; factual claims remain tied to their cited evidence.
