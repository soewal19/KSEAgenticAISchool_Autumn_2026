# Стек технологий — Air Alerts Forecast

Полный перечень технологий, методологий и паттернов, использованных в проекте,
с обоснованием выбора.

---

## 1. Язык и среда

| Технология | Версия | Назначение |
|------------|--------|------------|
| **Python** | 3.11+ | Основной язык реализации |
| **pip** | — | Управление зависимостями (`requirements.txt`) |

---

## 2. Методологии и инженерные паттерны

### 2.1 AI-DLC (AI Development Lifecycle)
Методология разработки AI-систем, структурирующая жизненный цикл от
сбора требований до деплоя и мониторинга. Применена для организации
этапов: **сбор данных → аудит → EDA → feature engineering → моделирование →
оценка → валидация утечек → рефакторинг**.

### 2.2 SDD (Specification-Driven Development)
Сначала формализована спецификация (target, признаки, метрики, гарантии
no-leakage), затем реализация. Конфигурация через [config.yaml](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/config.yaml)
с Pydantic-валидацией выступает как executable spec.

### 2.3 Walking Skeleton
Первой собрана минимальная end-to-end цепочка (загрузка → бинарный ряд →
target → features → baseline → метрики), затем её наполняли деталями. Это
гарантирует, что пайплайн всегда работоспособен на каждом шаге итерации.

### 2.4 Ports & Adapters (Гексагональная архитектура)
- **Port:** интерфейс доступа к данным (загрузка CSV).
- **Adapter:** [data_loader.py](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/data_loader.py) — HTTP-адаптер к GitHub-репозиторию датасета.
- Бизнес-логика (preprocessing, features, labels, models) изолирована от
  источника данных — можно заменить CSV на API без изменения ядра.

### 2.5 Test-First Thinking
Перед финальной реализацией core-трансформаций написаны тесты
([tests/test_pipeline.py](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/tests/test_pipeline.py)),
а для критического инварианта — отдельный валидатор
([validate_no_leakage.py](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/validate_no_leakage.py)).

### 2.6 C4 Model
Документация архитектуры на трёх уровнях (C1 Context, C2 Container,
C3 Component) — см. [docs/C4.md](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/docs/C4.md).

### 2.7 Convergence / Divergence (SSD)
На этапе выбора моделей исследовано множество подходов (baselines + 3 ML-модели),
затем выбрана лучшая по validation (Random Forest) — convergence.

---

## 3. Библиотеки анализа данных и ML

| Библиотека | Назначение в проекте |
|------------|----------------------|
| **pandas** 2.2 | Загрузка CSV, очистка, развёртывание интервалов в временной ряд, feature engineering, chronological split |
| **numpy** 2.1 | Векторизованные вычисления, rolling-окна, sin/cos кодирование |
| **scikit-learn** 1.5 | LogisticRegression, RandomForestClassifier, StandardScaler, метрики (PR-AUC, ROC-AUC, F1, Brier, confusion matrix), permutation_importance |
| **LightGBM** 4.6 | Градиентный бустинг (LGBMClassifier с `scale_pos_weight` для дисбаланса) |
| **matplotlib** + **seaborn** | Визуализация EDA, калибровочных кривых, feature importance |

> SHAP заявлен в `requirements.txt` как опциональный; в окружении не
> установлен, поэтому используется встроенный `permutation_importance`
> (model-agnostic, не требует дополнительных зависимостей).

---

## 4. Конфигурация и валидация

| Технология | Назначение |
|------------|------------|
| **PyYAML** | Парсинг `config.yaml` |
| **Pydantic v2** | Строгая валидация конфигурации ([config.py](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/config.py)), type hints на уровне схемы |

---

## 5. Ввод-вывод и хранилище

| Технология | Назначение |
|------------|------------|
| **requests** | HTTP-загрузка датасета с GitHub |
| **PyArrow** | Сериализация features+target и predictions в формат Parquet |
| **JSON / CSV** | Сохранение метрик и отчётов о деградации |

---

## 6. Качество данных и валидация утечек

| Компонент | Назначение |
|-----------|------------|
| `audit_data_quality` ([data_loader.py](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/data_loader.py)) | Schema, missing, duplicates, диапазон дат, регионы — без выдумок |
| `validate_no_leakage.py` | 23 проверки: хронология сплита, past-only лаги, отсутствие NaN/Inf, корректность target, нет target в фичах |

---

## 7. Тестирование

| Технология | Назначение |
|------------|------------|
| **pytest** | 8 unit-тестов core-трансформаций (cleaning, expansion, alert_starts, target, split, lag causality) |

---

## 8. Оркестрация и CLI

| Технология | Назначение |
|------------|------------|
| **argparse** | CLI `python -m src.pipeline {data,features,train,evaluate,all}` |
| **Makefile** | `make data/features/train/evaluate/all/test/validate-leakage` (Linux/macOS/CI) |
| **logging** (stdlib) | Логирование этапов в stdout с timestamps |

---

## 9. Документация

| Файл | Содержание |
|------|------------|
| [README.md](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/README.md) | Методология, схема пайплайна, метрики, ограничения, запуск |
| [docs/C4.md](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/docs/C4.md) | C1/C2/C3 + научные ссылки |
| [docs/TASK.md](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/docs/TASK.md) | Описание задания |
| [docs/TECHNOLOGIES.md](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/docs/TECHNOLOGIES.md) | Этот файл |

---

## 10. Ключевые инженерные решения

- **Хронологический сплит** train/val/test без shuffle — защита от look-ahead.
- **Forward-looking target** через `rolling().sum().shift(-H)` — исключает
  текущую ячейку, хвост помечается NaN.
- **Cold-start заполнение**: лаговые NaN в начале ряда заполняются `0`
  (нет наблюдения «до начала»), что проверено в валидаторе.
- **Scaler fit только на train**, **threshold — только на validation**.
- **`class_weight='balanced'`** (LR, RF) и **`scale_pos_weight`** (LightGBM)
  для борьбы с дисбалансом ~2.8%.
- **Permutation importance** на сэмпле (20k строк, 3 повтора) — интерпретируемость
  без тяжёлой зависимости от SHAP.
- **Degradation-over-time**: тест разбит на 4 хронологических окна для
  детекции нестационарности.
