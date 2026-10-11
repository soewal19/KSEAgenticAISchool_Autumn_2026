"""Modeling Hypothesis Agent.

Generates hypotheses about features and model architecture, including
MACD-like momentum, rolling counts, and neighbor lags.

The agent proposes concrete feature transformations that can be added to
the feature matrix and tested for PR-AUC improvement on validation.
"""
from __future__ import annotations

import pandas as pd

from .schema import AgentRole, Hypothesis


class ModelingAgent:
    role = AgentRole.MODELING

    def __init__(self, target_series: pd.Series, neighbor_series: dict[str, pd.Series], freq_minutes: int):
        self.series = target_series.fillna(0).astype(int)
        self.neighbors = neighbor_series
        self.freq = freq_minutes

    def generate(self) -> list[Hypothesis]:
        hyps: list[Hypothesis] = []

        # MACD-like momentum: fast EMA - slow EMA of alert activity
        hyps.append(Hypothesis(
            id="MODELING-001",
            agent=self.role,
            title="MACD-like momentum of alert activity (fast 15m - slow 60m EMA)",
            description=(
                "Momentum of recent alert activity relative to longer baseline. "
                "Positive momentum = activity accelerating (rising alert probability); "
                "negative = decelerating. Computed as EMA(15m) - EMA(60m) of binary series."
            ),
            feature_changes=["momentum_macd_15_60"],
            expected_effect="+PR-AUC via momentum of alert activity",
        ))

        # Rolling alert count of target in last 30 min
        hyps.append(Hypothesis(
            id="MODELING-002",
            agent=self.role,
            title="Target rolling alert count (30m window)",
            description=(
                "Number of active-alert cells in target region over last 30 minutes. "
                "High recent activity suggests ongoing wave; near-zero suggests quiet period."
            ),
            feature_changes=["target_rolling_30m"],
            expected_effect="+PR-AUC via recent-activity intensity",
        ))

        # Neighbor lag ensemble: max across neighbors at lag 5
        hyps.append(Hypothesis(
            id="MODELING-003",
            agent=self.role,
            title="Neighbor activity ensemble (max across neighbors at lag 5m)",
            description=(
                "Maximum alert-active indicator across all neighbors at 5m lag. "
                "If ANY neighbor is active, regional wave likely; robust to which neighbor."
            ),
            feature_changes=["neighbor_max_lag_5m"],
            expected_effect="+PR-AUC via robust regional signal",
        ))

        # Time-since-last-alert binned (already in features, but hypothesis: interaction)
        hyps.append(Hypothesis(
            id="MODELING-004",
            agent=self.role,
            title="Recency x current-alert interaction",
            description=(
                "Interaction: time_since_last_alert_min * (1 - current_alert_duration_min>0). "
                "Captures whether a long quiet period followed by no active alert predicts a start."
            ),
            feature_changes=["recency_interaction"],
            expected_effect="+PR-AUC via recency-state interaction",
        ))

        return hyps
