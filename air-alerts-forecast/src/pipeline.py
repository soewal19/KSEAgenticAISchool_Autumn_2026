"""End-to-end pipeline orchestrator.

Stages:
  data      -> load, audit, clean intervals, save EDA plots
  features  -> build feature matrix + target, save to outputs
  train     -> fit all models, select thresholds on val, save artifacts
  evaluate  -> compute metrics on test, save figures/metrics/predictions
  all       -> run data -> features -> train -> evaluate
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import AppConfig, load_config
from .contracts import (
    DataAuditResult,
    FeatureSetResult,
    PipelineValidationResult,
)
from .data_loader import load_raw
from .evaluation import (
    calibration_curve,
    compute_metrics,
    compute_permutation_importance,
    degradation_over_time,
    error_examples,
    print_metrics_table,
    save_metrics,
)
from .features import build_features, split_train_val_test
from .labels import make_target
from .logger import get_logger
from .models import fit_model
from .plots import (
    plot_alert_counts_by_region,
    plot_alert_durations,
    plot_alert_durations_by_region,
    plot_calibration_curves,
    plot_cross_region_correlation,
    plot_feature_importance,
    plot_hourly_activity,
    plot_inter_alert_intervals,
    plot_monthly_activity,
    plot_weekday_activity,
    plot_yearly_patterns,
)
from .preprocessing import build_multi_region_frame, clean_intervals
from .validate_no_leakage import (
    Checker,
    check_chronological_split,
    check_lag_features_not_future,
    check_no_nan_inf,
    check_no_target_in_features,
    check_target_correctness,
)

logger = get_logger("pipeline")


def run_data_stage(config: AppConfig, raw: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load, clean, and produce EDA plots. Returns (intervals, binary_frame)."""
    raw = load_raw(config) if raw is None else raw
    intervals = clean_intervals(raw)
    regions = [config.regions.target] + config.regions.neighbors
    frame = build_multi_region_frame(intervals, regions, config.time.freq_minutes)
    out = Path(config.outputs.figures_dir)
    plot_alert_counts_by_region(intervals, out)
    plot_alert_durations_by_region(intervals, out)
    for r in regions:
        if r in frame.columns:
            plot_hourly_activity(frame[r], out, r.replace(" ", "_"))
            plot_weekday_activity(frame[r], out, r.replace(" ", "_"))
            plot_monthly_activity(frame[r], out, r.replace(" ", "_"))
            plot_inter_alert_intervals(frame[r], out, r.replace(" ", "_"))
            plot_alert_durations(intervals, r, out)
            plot_yearly_patterns(frame[r], out, r.replace(" ", "_"))
    plot_cross_region_correlation(frame, out)
    return intervals, frame


def run_features_stage(config: AppConfig, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build feature matrix and target. Returns (features, target)."""
    target_series = frame[config.regions.target]
    neighbors = {r: frame[r] for r in config.regions.neighbors if r in frame.columns}
    X = build_features(target_series, neighbors, config)
    y = make_target(target_series, config.time.horizon_minutes, config.time.freq_minutes)
    Xy = X.copy()
    Xy["target"] = y
    out = Path(config.outputs.predictions_dir)
    out.mkdir(parents=True, exist_ok=True)
    Xy.reset_index().rename(columns={"index": "timestamp"}).to_parquet(
        out / "features_target.parquet"
    )
    logger.info("Saved features+target to %s", out / "features_target.parquet")
    return X, y


def run_validation_stage(
    config: AppConfig,
    X: pd.DataFrame,
    y: pd.Series,
    target_series: pd.Series,
) -> PipelineValidationResult:
    """Run leakage & split checks. Must pass before training.

    Uses the deterministic checks from ``validate_no_leakage``. The gate
    rejects the pipeline if any check fails, preventing model training on
    leaked or mis-split data.
    """
    c = Checker()
    check_chronological_split(X, config, c)
    check_no_nan_inf(X, c)
    check_target_correctness(
        target_series, y, config.time.horizon_minutes, config.time.freq_minutes, c
    )
    check_lag_features_not_future(X, target_series, config, c)
    check_no_target_in_features(X, c)
    c.check(
        "Feature index equals target index (aligned)",
        X.index.equals(y.index),
        "features and target share index",
    )

    failed = [name for name, ok, _ in c.results if not ok]
    split_ok = all(
        ok for name, ok, _ in c.results if name.startswith(("Train", "Val", "Test", "No index"))
    )
    result = PipelineValidationResult(
        leakage_passed=len(failed) == 0,
        failed_rules=failed,
        split_is_chronological=split_ok,
        threshold_source="validation",
    )
    if not result.leakage_passed:
        logger.error("Pipeline validation FAILED: %s", failed)
    else:
        logger.info("Pipeline validation PASSED (%d checks)", len(c.results))
    return result


def run_train_stage(
    config: AppConfig, X: pd.DataFrame, y: pd.Series
) -> dict:
    """Fit all models, save artifacts. Returns dict of fitted artifacts."""
    Xtr, Xval, Xte = split_train_val_test(X, config.split.train_end, config.split.val_end)
    ytr, yval, yte = split_train_val_test(y.to_frame("target"), config.split.train_end, config.split.val_end)
    ytr, yval, yte = ytr["target"], yval["target"], yte["target"]

    mask_tr = ytr.notna()
    mask_va = yval.notna()
    Xtr, ytr = Xtr[mask_tr], ytr[mask_tr]
    Xval, yval = Xval[mask_va], yval[mask_va]

    artifacts: dict = {}
    for name in config.models:
        model, scaler, threshold, val_metrics = fit_model(
            name, Xtr, ytr, Xval, yval, config
        )
        artifacts[name] = {
            "model": model,
            "scaler": scaler,
            "threshold": threshold,
            "val_metrics": val_metrics,
        }
    artifacts["_splits"] = {"X_train": Xtr, "X_val": Xval, "X_test": Xte, "y_train": ytr, "y_val": yval, "y_test": yte}
    return artifacts


def run_evaluate_stage(config: AppConfig, artifacts: dict) -> dict:
    """Evaluate all models on test, save metrics/figures/predictions.

    Returns a dict with ``metrics`` (per-model test metrics) and
    ``best_model`` (name of the model with highest PR-AUC).
    """
    splits = artifacts["_splits"]
    Xte, yte = splits["X_test"], splits["y_test"]
    mask_te = yte.notna()
    Xte, yte = Xte[mask_te], yte[mask_te]

    persistence_proba = None
    if "persistence" in artifacts:
        persistence_proba = artifacts["persistence"]["model"].predict_proba(Xte)[:, 1]

    all_metrics: dict[str, dict] = {}
    predictions = pd.DataFrame(index=Xte.index)
    predictions["y_true"] = yte.values

    for name, art in artifacts.items():
        if name == "_splits":
            continue
        model = art["model"]
        scaler = art["scaler"]
        threshold = art["threshold"]
        X_eval = Xte if scaler is None else pd.DataFrame(scaler.transform(Xte), columns=Xte.columns, index=Xte.index)
        proba = model.predict_proba(X_eval)[:, 1]
        predictions[f"proba_{name}"] = proba
        metrics = compute_metrics(yte.values, proba, threshold, persistence_proba)
        all_metrics[name] = metrics

    print_metrics_table(all_metrics)

    metrics_dir = Path(config.outputs.metrics_dir)
    save_metrics(all_metrics, metrics_dir / config.outputs.metrics_filename)

    pred_dir = Path(config.outputs.predictions_dir)
    predictions.to_parquet(pred_dir / "test_predictions.parquet")

    curves = {}
    for name in all_metrics:
        curves[name] = calibration_curve(yte.values, predictions[f"proba_{name}"].values)
    plot_calibration_curves(curves, config.outputs.figures_dir)

    if "lightgbm" in artifacts:
        try:
            model = artifacts["lightgbm"]["model"]
            importances = pd.Series(model.feature_importances_, index=Xte.columns)
            plot_feature_importance(importances, config.outputs.figures_dir)
        except Exception as e:
            logger.warning("Could not plot feature importance: %s", e)

    best_model_name = max(
        (n for n in all_metrics if n != "_splits"),
        key=lambda n: all_metrics[n]["pr_auc"],
    )
    best_art = artifacts[best_model_name]
    best_model = best_art["model"]
    best_threshold = best_art["threshold"]
    best_proba = predictions[f"proba_{best_model_name}"].values

    try:
        if best_model_name in {"persistence", "seasonal"}:
            raise NotImplementedError("Permutation importance is not supported for the custom baseline models")
        X_eval_best = Xte if best_art["scaler"] is None else pd.DataFrame(
            best_art["scaler"].transform(Xte), columns=Xte.columns, index=Xte.index
        )
        sample_size = min(20000, len(X_eval_best))
        sample_idx = X_eval_best.sample(n=sample_size, random_state=config.project.random_state).index
        perm_imp = compute_permutation_importance(
            best_model, X_eval_best.loc[sample_idx], yte.loc[sample_idx],
            n_repeats=3, random_state=config.project.random_state,
        )
        plot_feature_importance(perm_imp, config.outputs.figures_dir, filename="permutation_importance.png")
        logger.info("Permutation importance (top 10):\n%s", perm_imp.head(10).to_string())
    except NotImplementedError as e:
        logger.debug("Skipping permutation importance: %s", e)
    except Exception as e:
        logger.warning("Could not compute permutation importance: %s", e)

    deg = degradation_over_time(yte, best_proba, best_threshold)
    deg_path = Path(config.outputs.metrics_dir) / "degradation_over_time.csv"
    deg.to_csv(deg_path, index=False)
    logger.info("Degradation over time:\n%s", deg.to_string(index=False))

    errs = error_examples(yte, best_proba, best_threshold)
    err_path = Path(config.outputs.metrics_dir) / "error_examples.txt"
    with open(err_path, "w", encoding="utf-8") as f:
        for kind, idx in errs.items():
            f.write(f"=== {kind} (best model: {best_model_name}) ===\n")
            for t in idx:
                f.write(f"  {t}\n")
    logger.info("Saved error examples to %s", err_path)

    return {"metrics": all_metrics, "best_model": best_model_name}


def main() -> None:
    parser = argparse.ArgumentParser(description="Air-alert forecasting pipeline")
    parser.add_argument("stage", choices=["data", "features", "train", "evaluate", "all"], default="all", nargs="?")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    logger.setLevel(config.project.log_level)

    # Persistence is deliberately optional: local Parquet remains the source of
    # truth for dense arrays, and no engine is created in offline mode.
    from .persistence import get_repository
    repository = get_repository()
    if repository is not None:
        repository.initialize()
        logger.info("Optional PostgreSQL persistence enabled")
    else:
        logger.info("DATABASE_URL not set; using offline/local files")
    dataset_version = "not-loaded"

    stage_order = {"data": 1, "features": 2, "train": 3, "evaluate": 4, "all": 4}
    level = stage_order[args.stage]

    data_audit: DataAuditResult | None = None
    if level >= 1:
        raw = load_raw(config)
        dataset_version = hashlib.sha256(
            raw.to_csv(index=False).encode("utf-8")
        ).hexdigest()
        if repository is not None:
            repository.upsert_alert_events(raw)
        if args.stage == "data":
            intervals, frame = run_data_stage(config, raw)
            if repository is not None:
                repository.upsert_cleaned_intervals(intervals)
        else:
            intervals = clean_intervals(raw)
            if repository is not None:
                repository.upsert_cleaned_intervals(intervals)
            regions = [config.regions.target] + config.regions.neighbors
            frame = build_multi_region_frame(intervals, regions, config.time.freq_minutes)

        # ---- Data stage contract ----
        target_series = frame[config.regions.target]
        data_audit = DataAuditResult(
            status="pass",
            rows=len(frame),
            regions=list(frame.columns),
            date_min=str(frame.index.min()),
            date_max=str(frame.index.max()),
            missing_values={c: int(frame[c].isna().sum()) for c in frame.columns},
            duplicates=int(intervals.duplicated().sum()) if not intervals.empty else 0,
            issues=[],
        )
        logger.info(
            "Data audit: rows=%d regions=%d range=%s..%s",
            data_audit.rows, len(data_audit.regions),
            data_audit.date_min, data_audit.date_max,
        )
        if repository is not None:
            from .data_loader import audit_data_quality
            report = audit_data_quality(raw)
            repository.record_quality_checks([
                {"check_name": "raw_duplicate_rows", "passed": report["duplicate_rows"] == 0,
                 "details_json": {"duplicate_rows": report["duplicate_rows"], "rows": len(raw)}},
                {"check_name": "cleaned_intervals_nonempty", "passed": not intervals.empty,
                 "details_json": {"interval_rows": len(intervals)}},
                {"check_name": "timestamps_utc", "passed": str(intervals["started_at"].dtype).endswith("UTC]"),
                 "details_json": {"started_at_dtype": str(intervals["started_at"].dtype)}},
            ])

    feature_set: FeatureSetResult | None = None
    if level >= 2:
        X, y = run_features_stage(config, frame)
        # ---- Features stage contract ----
        feature_set = FeatureSetResult(
            feature_names=list(X.columns),
            n_rows=len(X),
            causal_checks_passed=True,  # validated below in validation stage
            train_end=config.split.train_end,
            validation_end=config.split.val_end,
            test_start=config.split.val_end,
        )
        logger.info("Feature set: %d features x %d rows", len(feature_set.feature_names), feature_set.n_rows)

    if level >= 3:
        # ---- Validation gate: blocks training on failure ----
        validation = run_validation_stage(config, X, y, target_series)
        if not validation.leakage_passed:
            raise RuntimeError(
                f"Pipeline validation failed — training aborted. Failed rules: {validation.failed_rules}"
            )
        artifacts = run_train_stage(config, X, y)

    if level >= 4:
        eval_result = run_evaluate_stage(config, artifacts)
        all_metrics = eval_result["metrics"]
        best_model = eval_result["best_model"]

        # ---- Run log: auditable record of this run ----
        from .run_log import build_run_log, save_run_log

        run_log = build_run_log(
            config=config,
            feature_names=list(X.columns),
            n_rows=len(X),
            data_min=str(X.index.min()),
            data_max=str(X.index.max()),
            best_model=best_model,
            models_evaluated=list(all_metrics.keys()),
            metrics=all_metrics,
        )
        run_log_path = save_run_log(run_log)
        logger.info("Run log saved to %s (run_id=%s)", run_log_path, run_log.run_id)
        if repository is not None:
            def utc_boundary(value: str) -> datetime:
                ts = pd.Timestamp(value)
                ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
                return ts.to_pydatetime()

            try:
                git_commit = subprocess.run(
                    ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
                    text=True, timeout=5,
                ).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                git_commit = None
            for model_name, metrics in all_metrics.items():
                repository.record_experiment_run(
                    run_id=uuid.uuid4(), config_hash=run_log.config_hash,
                    git_commit=git_commit, dataset_version=dataset_version,
                    model_name=model_name,
                    forecast_horizon_minutes=config.time.horizon_minutes,
                    train_end=utc_boundary(config.split.train_end),
                    validation_end=utc_boundary(config.split.val_end),
                    test_end=utc_boundary(str(X.index.max())), metrics=metrics,
                )


if __name__ == "__main__":
    main()
