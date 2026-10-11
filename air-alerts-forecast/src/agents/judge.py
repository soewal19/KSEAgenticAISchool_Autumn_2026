"""Judge Agent.

Accepts a hypothesis ONLY if ALL of the following hold:
  1. Leakage test PASS (no look-ahead, no NaN/Inf).
  2. Validation PR-AUC improves over baseline.
  3. Improvement is stable across rolling-origin folds (>= 2/3 folds better).
  4. Result is reproducible (same seed → same PR-AUC).

Agent consensus is NOT proof — only metrics and tests decide.
"""
from __future__ import annotations

from .schema import HypothesisStatus, JudgeDecision, ValidationResult


class JudgeAgent:
    MIN_FOLDS_IMPROVED = 2
    MIN_FOLDS_TOTAL = 2

    def decide(self, validation: ValidationResult) -> JudgeDecision:
        reasons: list[str] = []

        leakage_pass = validation.leakage_test_pass
        if not leakage_pass:
            reasons.append("leakage test FAILED")

        pr_auc_improved = validation.hypothesis_pr_auc > validation.baseline_pr_auc
        if not pr_auc_improved:
            reasons.append(
                f"PR-AUC did not improve: {validation.hypothesis_pr_auc:.4f} "
                f"<= baseline {validation.baseline_pr_auc:.4f}"
            )

        stable = (
            validation.total_folds >= self.MIN_FOLDS_TOTAL
            and validation.folds_improved >= self.MIN_FOLDS_IMPROVED
        )
        if not stable:
            reasons.append(
                f"improvement not stable: {validation.folds_improved}/{validation.total_folds} "
                f"folds improved (need >= {self.MIN_FOLDS_IMPROVED})"
            )

        reproducible = validation.reproducible
        if not reproducible:
            reasons.append("result not reproducible across identical seeds")

        accepted = leakage_pass and pr_auc_improved and stable and reproducible

        reason = "; ".join(reasons) if reasons else "all judge criteria satisfied"
        return JudgeDecision(
            hypothesis_id=validation.hypothesis_id,
            leakage_pass=leakage_pass,
            pr_auc_improved=pr_auc_improved,
            stable_across_folds=stable,
            reproducible=reproducible,
            accepted=accepted,
            reason=reason,
        )

    @staticmethod
    def status_after(decision: JudgeDecision) -> HypothesisStatus:
        return (
            HypothesisStatus.ACCEPTED
            if decision.accepted
            else HypothesisStatus.REJECTED
        )
