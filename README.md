# KSE Agentic AI School — Autumn 2026

An agentic research project on forecasting air-raid alerts in Ukraine.

## Project structure

- [`air-alerts-forecast/`](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/tree/main/air-alerts-forecast) — the main project repository, containing an ML pipeline that forecasts the probability of new air-raid alerts by region. See [`air-alerts-forecast/README.md`](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/blob/main/air-alerts-forecast/README.md) for the project overview, methodology, and setup instructions.
- [`air-alerts-forecast/docs/`](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/tree/main/air-alerts-forecast/docs) — assignment brief (`TASK.md`), technology stack (`TECHNOLOGIES.md`), and architecture (`C4.md`).
- [`air-alerts-forecast/src/`](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/tree/main/air-alerts-forecast/src) — pipeline source code.
- [`air-alerts-forecast/tests/`](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/tree/main/air-alerts-forecast/tests) — project tests.

## Quick start

~~~bash
cd air-alerts-forecast
pip install -r requirements.txt
python -m src.pipeline all --config config.smoke.yaml
~~~

## License

[MIT](https://github.com/soewal19/KSEAgenticAISchool_Autumn_2026/blob/main/LICENSE)
