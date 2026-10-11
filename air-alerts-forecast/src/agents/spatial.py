"""Spatial Hypothesis Agent.

Generates hypotheses about regional convergence/divergence and lead-lag
spillover between Kyiv City and neighboring oblasts.

Hypotheses are data-driven: the agent inspects cross-region correlations
at different lags and proposes features that exploit the strongest
spatial signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import AgentRole, Hypothesis


class SpatialAgent:
    role = AgentRole.SPATIAL

    def __init__(self, frame: pd.DataFrame, target: str, neighbors: list[str], freq_minutes: int):
        self.frame = frame
        self.target = target
        self.neighbors = neighbors
        self.freq = freq_minutes

    def _lag_correlation(self, a: pd.Series, b: pd.Series, max_lag_min: int = 60) -> dict[int, float]:
        corrs: dict[int, float] = {}
        for lag in [1, 5, 15, 30, 60]:
            steps = max(1, lag // self.freq)
            c = a.corr(b.shift(steps))
            corrs[lag] = float(c) if not np.isnan(c) else 0.0
        return corrs

    def generate(self) -> list[Hypothesis]:
        hyps: list[Hypothesis] = []

        target = self.frame[self.target].fillna(0).astype(int)
        # target alert-START indicator as the phenomenon to predict
        target_starts = (target == 1) & (target.shift(1).fillna(0) == 0)

        # Find the neighbor with the strongest lag correlation with target starts.
        # Initialize best_corr to 0.0 so any non-zero correlation (|c| > 0) updates
        # the best neighbor. Using -1.0 would make the condition abs(c) > abs(-1.0)
        # = abs(c) > 1.0 never true for Pearson correlations in [-1, 1].
        best_neighbor, best_lag, best_corr = None, None, 0.0
        for nb in self.neighbors:
            nb_series = self.frame[nb].fillna(0).astype(int)
            corrs = self._lag_correlation(target_starts.astype(int), nb_series)
            for lag, c in corrs.items():
                if abs(c) > abs(best_corr):
                    best_neighbor, best_lag, best_corr = nb, lag, c

        if best_neighbor is not None:
            hyps.append(Hypothesis(
                id="SPATIAL-001",
                agent=self.role,
                title=f"Lead-lag spillover from {best_neighbor} (lag {best_lag}m)",
                description=(
                    f"{best_neighbor} alert activity at lag {best_lag}m has the strongest "
                    f"correlation ({best_corr:.3f}) with Kyiv City alert starts. "
                    f"Adding neighbor lags should improve PR-AUC."
                ),
                feature_changes=[f"nb_{best_neighbor.replace(' ', '_')}_lag_{best_lag}m"],
                expected_effect="+PR-AUC via spatial spillover signal",
            ))

        # Hypothesis: neighbor rolling alert count captures regional wave
        for nb in self.neighbors[:1]:
            hyps.append(Hypothesis(
                id="SPATIAL-002",
                agent=self.role,
                title=f"Regional wave: rolling alert count in {nb} (30m window)",
                description=(
                    f"Count of active-alert cells in {nb} over the last 30 minutes "
                    f"captures whether a regional wave is approaching Kyiv City."
                ),
                feature_changes=[f"nb_{nb.replace(' ', '_')}_rolling_30m"],
                expected_effect="+PR-AUC via regional wave detection",
            ))

        # Hypothesis: cross-region divergence (Kyiv active but neighbors not = isolated event)
        hyps.append(Hypothesis(
            id="SPATIAL-003",
            agent=self.role,
            title="Cross-region divergence: Kyiv isolated vs regional wave",
            description=(
                "If Kyiv City has an active alert but all neighbors are quiet, "
                "the event is likely isolated and less likely to re-trigger. "
                "Conversely, many active neighbors signal an incoming wave."
            ),
            feature_changes=["neighbors_active_count"],
            expected_effect="+PR-AUC by distinguishing isolated vs regional events",
        ))

        return hyps
