"""Data loading adapter for the Ukrainian air-raid siren dataset.

Adapter port: fetches the historical siren dataset (intervals of alerts
per region) from the public GitHub repository and loads it into memory.
Also exposes a data-quality audit that reports schema, ranges, regions,
missing values and duplicates without fabricating any field names.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests

from .config import AppConfig, load_config
from .logger import get_logger

logger = get_logger("data_loader")


def download_if_needed(url: str, dest: str | Path, timeout: int = 60) -> Path:
    """Download the dataset file if it does not already exist locally.

    Args:
        url: Remote URL of the CSV dataset.
        dest: Local destination path.
        timeout: HTTP timeout in seconds.

    Returns:
        Resolved local path of the dataset.
    """
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("Dataset already present at %s (%d bytes)", dest, dest.stat().st_size)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading dataset from %s", url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info("Saved dataset to %s (%d bytes)", dest, dest.stat().st_size)
    return dest


def load_raw(config: AppConfig) -> pd.DataFrame:
    """Load the raw siren intervals dataset.

    Args:
        config: Application configuration.

    Returns:
        Raw DataFrame as-is from the CSV.
    """
    path = download_if_needed(config.data.source_url, config.data.raw_path)
    df = pd.read_csv(path)
    logger.info("Loaded raw dataset: %d rows, %d columns", len(df), len(df.columns))
    return df


def audit_data_quality(df: pd.DataFrame) -> dict:
    """Compute a data-quality audit report from the raw DataFrame.

    The report contains only facts derivable from the data itself:
    schema (dtypes), shape, date range, unique regions, missing counts,
    duplicate rows and a preview of the first rows.

    Args:
        df: Raw intervals DataFrame.

    Returns:
        Dictionary with audit metrics.
    """
    report: dict = {}
    report["shape"] = {"rows": int(len(df)), "columns": int(len(df.columns))}
    report["columns"] = {c: str(df[c].dtype) for c in df.columns}

    report["missing"] = {
        c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()
    }
    report["total_missing_cells"] = int(df.isna().sum().sum())

    dup_mask = df.duplicated()
    report["duplicate_rows"] = int(dup_mask.sum())

    report["head"] = df.head(20).to_dict(orient="records")

    report["unique_values"] = {
        c: int(df[c].nunique(dropna=True)) for c in df.columns
    }
    return report


def infer_time_columns(df: pd.DataFrame) -> list[str]:
    """Return column names whose dtype is datetime-like or that look like timestamps.

    Args:
        df: Raw DataFrame.

    Returns:
        List of detected time column names.
    """
    time_cols: list[str] = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            time_cols.append(col)
            continue
        sample = df[col].dropna().astype(str).head(50)
        if sample.empty:
            continue
        try:
            pd.to_datetime(sample, errors="raise")
            time_cols.append(col)
        except (ValueError, TypeError):
            continue
    return time_cols


def parse_time_columns(df: pd.DataFrame, time_cols: list[str]) -> pd.DataFrame:
    """Parse detected time columns to datetime in-place copy."""
    out = df.copy()
    for col in time_cols:
        out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)
    return out


def print_audit_report(report: dict, df: pd.DataFrame) -> None:
    """Pretty-print the data-quality audit report to stdout."""
    print("=" * 72)
    print("DATA QUALITY AUDIT REPORT")
    print("=" * 72)
    print(f"Shape: {report['shape']['rows']} rows x {report['shape']['columns']} columns")
    print("\nSchema (column -> dtype):")
    for c, d in report["columns"].items():
        print(f"  {c:<30} {d}")

    print("\nMissing values (only non-zero shown):")
    if report["missing"]:
        for c, n in report["missing"].items():
            print(f"  {c:<30} {n}")
    else:
        print("  (none)")
    print(f"  Total missing cells: {report['total_missing_cells']}")

    print(f"\nDuplicate rows: {report['duplicate_rows']}")

    time_cols = infer_time_columns(df)
    print(f"\nDetected time columns: {time_cols}")
    if time_cols:
        parsed = parse_time_columns(df, time_cols)
        for col in time_cols:
            s = parsed[col].dropna()
            if not s.empty:
                print(f"  {col}: min={s.min()}  max={s.max()}")

    region_cols = [c for c in df.columns if df[c].dtype == object and df[c].nunique(dropna=True) < 100]
    if region_cols:
        print("\nPotential region/categorical columns and unique counts:")
        for c in region_cols:
            print(f"  {c}: {df[c].nunique(dropna=True)} unique values")
            vals = df[c].dropna().unique()[:30]
            print(f"      sample: {list(vals)}")

    print("\nFirst 20 rows:")
    print(df.head(20).to_string(index=False))
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load & audit the siren dataset")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--audit", action="store_true", help="Print data quality audit")
    args = parser.parse_args()

    config = load_config(args.config)
    df = load_raw(config)
    if args.audit:
        report = audit_data_quality(df)
        print_audit_report(report, df)


if __name__ == "__main__":
    main()
