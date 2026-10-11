"""Temporal Hypothesis Agent.

Generates hypotheses about hour-of-day, day-of-week, seasonality, and
regime changes. Data-driven: the agent measures alert-start rates across
calendar dimensions and proposes features for the strongest signal.
"""
from __future__ import annotations

import pandas as pd

from .schema import AgentRole, Hypothesis


class TemporalAgent:
    role = AgentRole.TEMPORAL

    def __init__(self, target_series: pd.Series, freq_minutes: int):
        self.series = target_series.fillna(0).astype(int)
        self.freq = freq_minutes
        self.starts = (self.series == 1) & (self.series.shift(1).fillna(0) == 0)

    def _rate_by(self, dim: pd.Series) -> pd.Series:
        df = pd.DataFrame({"start": self.starts.astype(int), "dim": dim})
        return df.groupby("dim")["start"].mean()

    def generate(self) -> list[Hypothesis]:
        hyps: list[Hypothesis] = []
        idx = self.series.index

        # Hourly start rate
        hour_rate = self._rate_by(idx.hour)
        peak_hour = int(hour_rate.idxmax())
        peak_rate = float(hour_rate.max())
        hyps.append(Hypothesis(
            id="TEMPORAL-001",
            agent=self.role,
            title=f"Peak-hour alert-start signal (peak hour {peak_hour})",
            description=(
                f"Alert-start rate peaks at hour {peak_hour} ({peak_rate:.4f}). "
                f"Hour-of-day (cyclic sin/cos) should capture this pattern."
            ),
            feature_changes=["hour_sin", "hour_cos"],
            expected_effect="+PR-AUC via diurnal seasonality",
        ))

        # Day-of-week
        dow_rate = self._rate_by(idx.dayofweek)
        hyps.append(Hypothesis(
            id="TEMPORAL-002",
            agent=self.role,
            title="Day-of-week seasonality in alert starts",
            description=(
                f"Alert-start rate varies by weekday (range "
                f"{dow_rate.min():.4f} - {dow_rate.max():.4f}). "
                f"Cyclic day-of-week encoding should capture weekly patterns."
            ),
            feature_changes=["dow_sin", "dow_cos", "is_weekend"],
            expected_effect="+PR-AUC via weekly seasonality",
        ))

        # Regime change: compare early vs late period start rates
        mid = len(self.series) // 2
        early_rate = self.starts.iloc[:mid].mean()
        late_rate = self.starts.iloc[mid:].mean()
        hyps.append(Hypothesis(
            id="TEMPORAL-003",
            agent=self.role,
            title="Regime change: days-since-war-start as non-stationarity feature",
            description=(
                f"Alert-start rate changed from {early_rate:.4f} (early) to "
                f"{late_rate:.4f} (late). Patterns are non-stationary; "
                f"days_since_war_start captures regime drift."
            ),
            feature_changes=["days_since_war_start"],
            expected_effect="+PR-AUC via regime-drift adaptation",
        ))

        # Month seasonality
        month_rate = self._rate_by(idx.month)
        hyps.append(Hypothesis(
            id="TEMPORAL-004",
            agent=self.role,
            title="Monthly seasonality in alert starts",
            description=(
                f"Alert-start rate varies by month (range "
                f"{month_rate.min():.4f} - {month_rate.max():.4f})."
            ),
            feature_changes=["month"],
            expected_effect="+PR-AUC via annual seasonality",
        ))

        return hyps
