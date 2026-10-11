# Data Card

## Dataset

The project uses the public historical Ukrainian air-raid alert interval dataset published in the [Vadimkin dataset repository](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset). The configured source file is official_data_en.csv.

## Intended use

The data supports retrospective, educational analysis of alert activity and short-horizon alert-onset classification. It is not intended for operational warning, emergency response, or personal safety decisions.

## Contents and processing

The source contains oblast, raion, hromada, administrative level, alert start and end timestamps, and source fields. The modelling path retains oblast- and raion-level intervals, groups both by parent oblast, discards hromada rows to avoid nested duplicates, parses timestamps as UTC, removes invalid/exact duplicate intervals, and unions overlaps into five-minute binary regional activity series.

The regions in the default configuration are Kyiv City, Kyivska oblast, Chernihivska oblast, and Sumska oblast. The primary target is Kyiv City.

## Temporal coverage

The source was fetched from the configured upstream URL on 2026-10-12. It contains 299,275 raw rows and spans 2022-03-15 through the latest alert start at 2026-09-07 05:28:22 UTC. The data digest is `b396f87696243069eec0219880e87dcd642b20beb0a7bae0d0e1f61e1ed20ec4`. The source returned the same bytes as the previous local copy, so no newer upstream records were available at refresh time. The full-run test predictions cover 2024-06-30 00:00 through 2026-09-07 05:05 UTC.

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
