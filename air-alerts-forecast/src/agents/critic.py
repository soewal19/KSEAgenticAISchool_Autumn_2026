"""Critic Agent.

Reviews each hypothesis for:
  - look-ahead bias (leakage from future)
  - lag correctness (lag L minutes = shift(L/freq) cells, L > 0)
  - reproducibility (depends only on fixed random_state, no random ops)
  - testability (has a clear measurable metric)

The Critic DOES NOT rewrite code. It only flags issues.
"""
from __future__ import annotations

import re

from .schema import CriticVerdict, Hypothesis


class CriticAgent:
    """Static rule-based critic. No code rewriting."""

    FORBIDDEN_FUTURE_PATTERNS = [
        r"shift\(-\d+\)",
        r"future",
        r"look.?ahead",
        r"rolling.*forward",
        r"lead\(",
    ]

    def review(self, hyp: Hypothesis) -> CriticVerdict:
        comments: list[str] = []

        # 1. Look-ahead bias: scan feature_changes for forward-looking patterns
        look_ahead = False
        for feat in hyp.feature_changes:
            for pat in self.FORBIDDEN_FUTURE_PATTERNS:
                if re.search(pat, feat, re.IGNORECASE):
                    look_ahead = True
                    comments.append(f"Feature '{feat}' matches forbidden future pattern: {pat}")

        # 2. Lag correctness: any 'lag_Xm' must have X > 0 and integer
        lag_correct = True
        for feat in hyp.feature_changes:
            m = re.search(r"lag_(\d+)m", feat)
            if m:
                lag = int(m.group(1))
                if lag <= 0:
                    lag_correct = False
                    comments.append(f"Feature '{feat}' has non-positive lag {lag}")

        # Rolling windows must be backward-looking (no 'forward' in name)
        for feat in hyp.feature_changes:
            if "rolling" in feat and "forward" in feat.lower():
                look_ahead = True
                comments.append(f"Rolling feature '{feat}' appears forward-looking")

        # 3. Reproducibility: hypotheses are deterministic feature additions,
        #    no randomness in feature construction. Model training uses fixed seed.
        reproducible = True
        if "random" in hyp.description.lower() and "seed" not in hyp.description.lower():
            reproducible = False
            comments.append("Description mentions randomness without seed specification")

        # 4. Testability: must have at least one feature change and a metric
        testable = True
        if not hyp.feature_changes and hyp.model_changes is None:
            testable = False
            comments.append("No feature or model changes specified — not testable")
        if not hyp.metric:
            testable = False
            comments.append("No evaluation metric specified")

        passed = (not look_ahead) and lag_correct and reproducible and testable

        if passed:
            comments.append("All critic checks passed")

        return CriticVerdict(
            hypothesis_id=hyp.id,
            look_ahead_bias=look_ahead,
            lag_correct=lag_correct,
            reproducible=reproducible,
            testable=testable,
            comments=comments,
            passed=passed,
        )
