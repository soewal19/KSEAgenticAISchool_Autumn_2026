"""EDA and analysis plots."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .logger import get_logger

logger = get_logger("plots")


def savefig(fig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    logger.info("Saved figure: %s", path)


def plot_alert_counts_by_region(intervals: pd.DataFrame, out_dir: str | Path) -> None:
    counts = intervals.groupby("oblast").size().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    counts.plot(kind="bar", ax=ax, color="steelblue")
    ax.set_title("Number of alert intervals by region")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=60)
    savefig(fig, Path(out_dir) / "alert_counts_by_region.png")


def plot_alert_durations_by_region(intervals: pd.DataFrame, out_dir: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    data = intervals.groupby("oblast")["duration_min"].median().sort_values(ascending=False)
    data.plot(kind="bar", ax=ax, color="darkorange")
    ax.set_title("Median alert duration by region (minutes)")
    ax.set_ylabel("Minutes")
    ax.tick_params(axis="x", rotation=60)
    savefig(fig, Path(out_dir) / "alert_durations_by_region.png")


def plot_hourly_activity(series: pd.Series, out_dir: str | Path, name: str = "target") -> None:
    df = pd.DataFrame({"active": series})
    df["hour"] = df.index.hour
    hourly = df.groupby("hour")["active"].mean()
    fig, ax = plt.subplots(figsize=(8, 4))
    hourly.plot(kind="bar", ax=ax, color="seagreen")
    ax.set_title(f"Hourly alert activity ({name})")
    ax.set_ylabel("Fraction active")
    ax.set_ylim(0, 1)
    savefig(fig, Path(out_dir) / f"hourly_activity_{name}.png")


def plot_weekday_activity(series: pd.Series, out_dir: str | Path, name: str = "target") -> None:
    df = pd.DataFrame({"active": series})
    df["dow"] = df.index.dayofweek
    dow = df.groupby("dow")["active"].mean()
    dow.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig, ax = plt.subplots(figsize=(7, 4))
    dow.plot(kind="bar", ax=ax, color="purple")
    ax.set_title(f"Weekday alert activity ({name})")
    ax.set_ylabel("Fraction active")
    ax.set_ylim(0, 1)
    savefig(fig, Path(out_dir) / f"weekday_activity_{name}.png")


def plot_monthly_activity(series: pd.Series, out_dir: str | Path, name: str = "target") -> None:
    df = pd.DataFrame({"active": series})
    df["month"] = df.index.month
    monthly = df.groupby("month")["active"].mean()
    fig, ax = plt.subplots(figsize=(8, 4))
    monthly.plot(kind="bar", ax=ax, color="crimson")
    ax.set_title(f"Monthly alert activity ({name})")
    ax.set_ylabel("Fraction active")
    ax.set_ylim(0, 1)
    savefig(fig, Path(out_dir) / f"monthly_activity_{name}.png")


def plot_cross_region_correlation(frame: pd.DataFrame, out_dir: str | Path) -> None:
    corr = frame.corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax, vmin=-1, vmax=1)
    ax.set_title("Cross-region alert activity correlation")
    savefig(fig, Path(out_dir) / "cross_region_correlation.png")


def plot_inter_alert_intervals(series: pd.Series, out_dir: str | Path, name: str = "target") -> None:
    s = series.fillna(0).astype(int)
    ends = (s == 0) & (s.shift(1).fillna(0) == 1)
    starts = (s == 1) & (s.shift(1).fillna(0) == 0)
    end_times = s.index[ends]
    start_times = s.index[starts]
    if len(end_times) == 0 or len(start_times) == 0:
        logger.warning("Cannot compute inter-alert intervals for %s", name)
        return
    gaps = []
    ei = 0
    for st in start_times:
        while ei < len(end_times) and end_times[ei] < st:
            prev_end = end_times[ei]
            gaps.append((st - prev_end).total_seconds() / 60.0)
            ei += 1
            break
    if not gaps:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(np.array(gaps), bins=50, color="teal", edgecolor="black")
    ax.set_title(f"Inter-alert interval distribution ({name})")
    ax.set_xlabel("Minutes between alerts")
    ax.set_ylabel("Count")
    ax.set_xlim(0, np.percentile(gaps, 99))
    savefig(fig, Path(out_dir) / f"inter_alert_intervals_{name}.png")


def plot_alert_durations(intervals: pd.DataFrame, region: str, out_dir: str | Path) -> None:
    reg = intervals[intervals["oblast"] == region]
    if reg.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(reg["duration_min"].values, bins=50, color="goldenrod", edgecolor="black")
    ax.set_title(f"Alert duration distribution ({region})")
    ax.set_xlabel("Minutes")
    ax.set_ylabel("Count")
    ax.set_xlim(0, np.percentile(reg["duration_min"], 99))
    savefig(fig, Path(out_dir) / f"alert_durations_{region.replace(' ', '_')}.png")


def plot_yearly_patterns(series: pd.Series, out_dir: str | Path, name: str = "target") -> None:
    df = pd.DataFrame({"active": series})
    df["year"] = df.index.year
    df["month"] = df.index.month
    pivot = df.groupby(["year", "month"])["active"].mean().unstack(level=0)
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(ax=ax, marker="o")
    ax.set_title(f"Yearly alert activity patterns ({name})")
    ax.set_ylabel("Fraction active")
    ax.set_xlabel("Month")
    ax.set_xticks(range(1, 13))
    savefig(fig, Path(out_dir) / f"yearly_patterns_{name}.png")


def plot_calibration_curves(curves: dict[str, pd.DataFrame], out_dir: str | Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
    for name, c in curves.items():
        if not c.empty:
            ax.plot(c["mean_predicted"], c["fraction_positive"], marker="o", label=name)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Calibration curves")
    ax.legend()
    savefig(fig, Path(out_dir) / "calibration_curves.png")


def plot_feature_importance(
    importances: pd.Series, out_dir: str | Path, top_n: int = 20,
    filename: str = "feature_importance.png",
) -> None:
    top = importances.abs().sort_values(ascending=False).head(top_n).sort_values()
    fig, ax = plt.subplots(figsize=(8, 8))
    top.plot(kind="barh", ax=ax, color="steelblue")
    ax.set_title(f"Top {top_n} feature importances")
    savefig(fig, Path(out_dir) / filename)
