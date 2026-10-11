# Technical Stack — Air Alerts Forecast

This page lists the main technologies and explains their role in the project.

## Language and runtime

| Technology | Role |
|---|---|
| Python 3.11 | Main implementation language and Docker runtime |
| pip | Installs dependencies from requirements.txt |

## Data and machine learning

| Library | Role |
|---|---|
| pandas | CSV loading, interval cleaning, time-grid construction, feature engineering, chronological splitting |
| NumPy | Vectorized calculations and cyclic time features |
| scikit-learn | Logistic regression, random forest, scaling, classification metrics, and permutation-importance utilities |
| LightGBM | Gradient-boosted tree model with class-imbalance weighting |
| matplotlib and seaborn | Exploratory plots, calibration, and feature diagnostics |
| PyArrow | Parquet serialization for feature and prediction matrices |

## Configuration and persistence

| Technology | Role |
|---|---|
| PyYAML | Reads project YAML configurations |
| Pydantic | Validates the application configuration |
| pydantic-settings | Reads optional DATABASE_URL settings from the environment and .env |
| SQLAlchemy 2 | PostgreSQL ORM and repository layer |
| psycopg 3 | PostgreSQL driver for Neon and local PostgreSQL |
| PostgreSQL / Neon | Optional storage for raw alert events, cleaned intervals, experiment runs, and data-quality checks |

Dense minute-level matrices stay in local Parquet files rather than PostgreSQL. The project supports an offline mode when DATABASE_URL is not set.

## Engineering and quality

| Tool | Role |
|---|---|
| pytest | Unit tests and an opt-in PostgreSQL integration test |
| Ruff | Python linting in CI |
| Docker | Reproducible Python 3.11 image built with multiple stages; runtime uses a non-root user |
| Docker Compose | Optional local PostgreSQL service for database testing |
| GitHub Actions | Lint, test, leakage validation, container build, and fixed-fixture smoke run; no registry push or deployment |
| argparse and Make | Pipeline CLI and common local tasks |
| Python logging | Timestamped stage and model logs |

## Key design choices

- Specification-driven development keeps target and leakage rules explicit in SPEC.md and tests.
- A small end-to-end smoke fixture provides deterministic feedback without downloading the full dataset.
- Chronological splitting prevents future observations from appearing in earlier partitions.
- Scalers are fit on training data, while thresholds are selected on validation.
- The optional persistence layer can be enabled without making a database a requirement for the forecasting pipeline.

See [the C4 architecture](C4.md) and [the methodology](methodology.md) for more detail.
