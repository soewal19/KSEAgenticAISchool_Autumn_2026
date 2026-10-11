"""Pydantic contracts for pipeline stage boundaries.

These models formalize the hand-off between pipeline stages so that each
stage can be gated on the previous stage's result. They mirror the
sequential multi-agent workflow pattern: every stage returns a structured
result, and a failed result blocks downstream stages.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DataAuditResult(BaseModel):
    """Result of the data loading & cleaning stage."""

    status: Literal["pass", "fail"]
    rows: int
    regions: list[str]
    date_min: str
    date_max: str
    missing_values: dict[str, int] = Field(default_factory=dict)
    duplicates: int
    issues: list[str] = Field(default_factory=list)


class FeatureSetResult(BaseModel):
    """Result of the feature engineering stage."""

    feature_names: list[str]
    n_rows: int
    causal_checks_passed: bool
    train_end: str
    validation_end: str
    test_start: str


class PipelineValidationResult(BaseModel):
    """Result of the leakage & split validation gate.

    If ``leakage_passed`` is False, the training stage must not run.
    """

    leakage_passed: bool
    failed_rules: list[str] = Field(default_factory=list)
    split_is_chronological: bool
    threshold_source: Literal["validation", "test", "none"] = "validation"
