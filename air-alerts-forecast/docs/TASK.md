# KSE Agentic Autumn 2026 — Stage 2 Assignment Summary

This page summarizes the Stage 2 brief for the project. The official application email and submission form remain the authoritative source for deadlines and submission instructions.

## Assignment

Build a small Python project for time-series analysis of air-raid alerts in Ukraine. The selection process evaluates both the result and the candidate's use of AI as a primary engineering tool: iteration, error correction, skepticism toward hallucinations, and guidance toward a working architecture.

## Objective

Create a reproducible research pipeline that estimates the probability of a new air-alert onset in a selected Ukrainian region over a short forecast horizon.

> This is not an early-warning system. Historical alerts reflect adversary actions and air-defence responses, not a natural cycle. Predictive power may be limited and must be reported honestly.

## Data and evaluation

- Source: [Vadimkin's Ukrainian air-raid siren dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset), file official_data_en.csv.
- Use the most recent available data and evaluate on the latest period.
- Prevent data leakage: neither training data nor model inputs may contain information from after the forecast timestamp.
- Optional news, official statements, or public-channel content must also have been published before the forecast timestamp.

## Expected analysis

- Main region: Kyiv City. Compare with relevant neighboring regions such as Kyivska, Chernihivska, and Sumska oblasts.
- Convert interval events to a regular binary series, using a one- or five-minute grid.
- Predict whether a new alert begins in (t, t + H], with H defaulting to 30 minutes and configurable alternatives of 15 or 60 minutes.
- Engineer only causal features, including lags, neighboring-region lags, alert duration and recency, rolling onset counts, and calendar variables.
- Compare baselines with machine-learning models. Select the decision threshold on validation only.
- Use PR-AUC as the primary metric for the imbalanced target. Also report ROC-AUC, precision, recall, F1, Brier score, calibration, confusion matrix, and baseline lift.
- Use exploratory plots to answer analytical questions: temporal changes, regional relationships, alert durations, calibration, model diagnostics, and performance degradation.

## Engineering expectations

- Python, YAML configuration, fixed random seeds, useful logging, docstrings, and type hints.
- Reproducible local execution, tests, and clear documentation of limitations.
- The repository includes pip and Docker workflows. Docker is optional for the researcher and CI uses a small fixed fixture rather than the full historical pipeline.

## Submission artifacts

1. A link to the GitHub repository containing the final working code.
2. A full text export of the AI conversation.
3. A plain-text reflection of about 100 words addressing what went wrong, how the approach changed, and why the final version is better than the first attempt.

The brief states a deadline of Monday, 12 October 2026 at 23:59 Kyiv time (EEST). Verify the deadline and form in the original email before submission.

## Evaluation emphasis

The AI interaction log is a primary signal. The committee looks for candidates who iterate, challenge incorrect or unsupported outputs, correct errors, and guide the AI toward a functional architecture instead of accepting the first answer uncritically.
