"""Multi-agent divergence-convergence orchestrator.

Protocol:
  Round 1 — DIVERGENCE: Spatial, Temporal, Modeling agents generate
            hypotheses independently.
  Round 2 — CRITIQUE: Critic reviews each hypothesis for look-ahead bias,
            lag correctness, reproducibility, testability. (No code rewrite.)
  Round 3 — EVIDENCE: Validation implements critic-passed hypotheses,
            checks leakage, computes validation PR-AUC, rolling-origin folds.
  Round 4 — CONVERGENCE: Judge accepts/rejects based on metrics + tests only.

Constraints:
  - max 3 rounds (here: one full round, as hypotheses are independent);
  - orchestrator is plain Python;
  - agents exchange Pydantic objects + JSON artifacts;
  - consensus is NOT proof; Validation/Judge decide on metrics+tests only;
  - rejected hypotheses saved to rejected_hypotheses.json with reason.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import AppConfig, load_config
from ..data_loader import load_raw
from ..features import build_features
from ..logger import get_logger
from ..preprocessing import build_multi_region_frame, clean_intervals
from .critic import CriticAgent
from .judge import JudgeAgent
from .modeling import ModelingAgent
from .schema import (
    Hypothesis,
    HypothesisStatus,
)
from .spatial import SpatialAgent
from .temporal import TemporalAgent
from .validation import ValidationAgent

logger = get_logger("agents.orchestrator")


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _to_jsonable(obj.model_dump())
    return obj


class MultiAgentOrchestrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.critic = CriticAgent()
        self.judge = JudgeAgent()
        self.rejected: list[dict] = []
        self.accepted: list[dict] = []

    def _prepare_data(self):
        raw = load_raw(self.config)
        intervals = clean_intervals(raw)
        regions = [self.config.regions.target] + self.config.regions.neighbors
        frame = build_multi_region_frame(intervals, regions, self.config.time.freq_minutes)
        target_series = frame[self.config.regions.target]
        neighbors = {r: frame[r] for r in self.config.regions.neighbors if r in frame.columns}
        X = build_features(target_series, neighbors, self.config)
        return frame, target_series, neighbors, X

    def run(self, output_dir: str | Path = "outputs/agents") -> dict:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        frame, target_series, neighbors, X = self._prepare_data()
        freq = self.config.time.freq_minutes

        # ---------- Round 1: DIVERGENCE ----------
        logger.info("=== Round 1: DIVERGENCE — independent hypothesis generation ===")
        spatial = SpatialAgent(frame, self.config.regions.target, self.config.regions.neighbors, freq)
        temporal = TemporalAgent(target_series, freq)
        modeling = ModelingAgent(target_series, neighbors, freq)

        hypotheses: list[Hypothesis] = []
        for agent in (spatial, temporal, modeling):
            hyps = agent.generate()
            hypotheses.extend(hyps)
            logger.info("%s generated %d hypotheses", agent.role, len(hyps))

        logger.info("Total hypotheses: %d", len(hypotheses))

        # Save divergence artifacts
        (output_dir / "hypotheses_proposed.json").write_text(
            json.dumps(_to_jsonable(hypotheses), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ---------- Round 2: CRITIQUE ----------
        logger.info("=== Round 2: CRITIQUE — leak/correctness/reproducibility review ===")
        critic_verdicts = {}
        passed_hyps: list[Hypothesis] = []
        for hyp in hypotheses:
            verdict = self.critic.review(hyp)
            critic_verdicts[hyp.id] = verdict
            if verdict.passed:
                hyp.status = HypothesisStatus.CRITIC_PASS
                passed_hyps.append(hyp)
                logger.info("[CRITIC PASS] %s: %s", hyp.id, hyp.title)
            else:
                hyp.status = HypothesisStatus.CRITIC_FAIL
                self.rejected.append({
                    "id": hyp.id,
                    "title": hyp.title,
                    "agent": hyp.agent.value,
                    "stage": "critic",
                    "reason": "; ".join(verdict.comments),
                })
                logger.warning("[CRITIC FAIL] %s: %s — %s", hyp.id, hyp.title, verdict.comments)

        (output_dir / "critic_verdicts.json").write_text(
            json.dumps(_to_jsonable(critic_verdicts), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ---------- Round 3: EVIDENCE ----------
        logger.info("=== Round 3: EVIDENCE — implement & validate (%d hypotheses) ===", len(passed_hyps))
        validation = ValidationAgent(self.config, X, target_series, neighbors)
        validation_results = {}
        for hyp in passed_hyps:
            logger.info("Validating %s: %s", hyp.id, hyp.title)
            res = validation.validate(hyp)
            validation_results[hyp.id] = res
            logger.info(
                "  PR-AUC baseline=%.4f hyp=%.4f delta=%+.4f folds_improved=%d/%d leak=%s repro=%s",
                res.baseline_pr_auc, res.hypothesis_pr_auc, res.pr_auc_delta,
                res.folds_improved, res.total_folds, res.leakage_test_pass, res.reproducible,
            )

        (output_dir / "validation_results.json").write_text(
            json.dumps(_to_jsonable(validation_results), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # ---------- Round 4: CONVERGENCE ----------
        logger.info("=== Round 4: CONVERGENCE — judge accept/reject ===")
        judge_decisions = {}
        for hyp_id, res in validation_results.items():
            decision = self.judge.decide(res)
            judge_decisions[hyp_id] = decision
            hyp = next(h for h in passed_hyps if h.id == hyp_id)
            hyp.status = self.judge.status_after(decision)
            if decision.accepted:
                self.accepted.append({
                    "id": hyp.id,
                    "title": hyp.title,
                    "agent": hyp.agent.value,
                    "pr_auc_delta": res.pr_auc_delta,
                    "folds_improved": res.folds_improved,
                    "reason": decision.reason,
                })
                logger.info("[ACCEPTED] %s: %s (ΔPR-AUC=%+.4f)", hyp.id, hyp.title, res.pr_auc_delta)
            else:
                self.rejected.append({
                    "id": hyp.id,
                    "title": hyp.title,
                    "agent": hyp.agent.value,
                    "stage": "judge",
                    "reason": decision.reason,
                    "pr_auc_delta": res.pr_auc_delta,
                    "folds_improved": res.folds_improved,
                })
                logger.warning("[REJECTED] %s: %s — %s", hyp.id, hyp.title, decision.reason)

        (output_dir / "judge_decisions.json").write_text(
            json.dumps(_to_jsonable(judge_decisions), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Save rejected hypotheses with reasons
        (output_dir / "rejected_hypotheses.json").write_text(
            json.dumps(self.rejected, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "accepted_hypotheses.json").write_text(
            json.dumps(self.accepted, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        summary = {
            "total_proposed": len(hypotheses),
            "critic_passed": len(passed_hyps),
            "critic_rejected": sum(1 for r in self.rejected if r["stage"] == "critic"),
            "judge_accepted": len(self.accepted),
            "judge_rejected": sum(1 for r in self.rejected if r["stage"] == "judge"),
            "accepted": self.accepted,
            "rejected": self.rejected,
        }
        (output_dir / "workflow_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "=== WORKFLOW COMPLETE: proposed=%d critic_pass=%d accepted=%d rejected=%d ===",
            summary["total_proposed"], summary["critic_passed"],
            summary["judge_accepted"], len(self.rejected),
        )
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent divergence-convergence workflow")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default="outputs/agents")
    args = parser.parse_args()

    config = load_config(args.config)
    orch = MultiAgentOrchestrator(config)
    summary = orch.run(args.output)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
