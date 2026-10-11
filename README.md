# KSEAgenticAISchool_Autumn_2026

Агентный исследовательский проект по прогнозированию воздушных тревог в Украине.

## Структура

- [`air-alerts-forecast/`](air-alerts-forecast) — основной репозиторий проекта:
  ML-пайплайн прогнозирования вероятности новых воздушных тревог по регионам.
  Подробное описание, методология, настройка запуска — в
  [`air-alerts-forecast/README.md`](air-alerts-forecast/README.md).
- [`air-alerts-forecast/docs/`](air-alerts-forecast/docs) — задание (TASK.md),
  стек технологий (TECHNOLOGIES.md), архитектура (C4.md).
- [`air-alerts-forecast/src/`](air-alerts-forecast/src) — исходный код пайплайна.
- [`air-alerts-forecast/tests/`](air-alerts-forecast/tests) — тесты.

## Быстрый старт

```bash
cd air-alerts-forecast
pip install -r requirements.txt
python -m src.pipeline all --config config.smoke.yaml
```

## Лицензия

[MIT](LICENSE)