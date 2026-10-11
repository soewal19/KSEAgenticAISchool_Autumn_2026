# Data Card

## Dataset

The project uses the public historical Ukrainian air-raid alert interval dataset published in the [Vadimkin dataset repository](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset). The configured source file is official_data_en.csv.

## Intended use

The data supports retrospective, educational analysis of alert activity and short-horizon alert-onset classification. It is not intended for operational warning, emergency response, or personal safety decisions.

## Contents and processing

The source contains oblast, raion, hromada, administrative level, alert start and end timestamps, and source fields. The current modelling path retains oblast-level intervals, parses timestamps as UTC, removes invalid and duplicate intervals, then constructs a five-minute regional activity series.

The regions in the default configuration are Kyiv City, Kyivska oblast, Chernihivska oblast, and Sumska oblast. The primary target is Kyiv City.

## Temporal coverage

The repository's current README records the source snapshot as spanning 2022-03-15 through 2026-09-07. The exact evaluation grid ends at the final interval available in the downloaded snapshot; the saved full-run test predictions currently cover 2024-06-30 00:00 UTC through 2026-09-05 23:10 UTC. Re-check the source when refreshing the data.

## Known limitations

- Historical alerts are observations of past outcomes, not a complete record of threat conditions.
- Data availability, reporting latency, and administrative-level duplication can affect interpretation.
- The model excludes external intelligence, news, and official statements.
- A five-minute activity grid summarizes intervals and does not preserve every detail in the source.
- Do not infer causality or operational predictability from correlations.

## Privacy and security

The configured source is public and does not require credentials. Optional Neon credentials belong in an untracked .env file or a CI secret. Do not place credentials in the dataset, documentation, or committed configuration.

## Versioning

The raw download is not committed. Optional database experiment records store a SHA-256 digest of the loaded raw rows as dataset_version. The fixed synthetic smoke fixture is committed separately at tests/fixtures/smoke_alerts.csv and must not be treated as observed alert history.
