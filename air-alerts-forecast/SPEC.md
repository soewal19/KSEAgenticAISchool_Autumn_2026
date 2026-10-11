# SPEC — Air Alerts Forecasting

Точная спецификация правил построения целевой переменной, разбиения данных,
каузальных признаков и выбора порога классификации. Любое изменение этих
правил должно отражаться здесь и в соответствующих тестах.

---

## 1. Целевая переменная (target)

**Задача:** бинарная классификация начала воздушной тревоги в целевом регионе
в интервале `(t, t + H]`, где `H` — горизонт прогноза (настраиваемый, по
умолчанию 30 мин).

### Формула

```
y_t = 1  iff  exists alert-start in (t, t + H]
y_t = 0  otherwise
y_t = NaN  for the last H cells (future not observed)
```

### Правила

- Интервал **строго открыт слева**: текущая ячейка `t` исключается.
- `alert-start` определяется как переход `0 -> 1` в бинарном ряду активности
  тревоги (не продолжение уже активной тревоги).
- `H` задаётся в минутах; число шагов = `max(1, H // freq_minutes)`.
- Частота сетки `freq_minutes` по умолчанию = 5 мин.
- Последние `H / freq_minutes` ячеек помечаются `NaN` и исключаются из
  обучения и оценки.

### Реализация

[`labels.make_target`](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/labels.py)
— forward rolling sum по индикатору начал, сдвинутый на `-H` шагов.

### Тесты

- `test_make_target_is_forward_looking` — `y_t` зависит только от будущего.
- `test_make_target_excludes_current_cell` — ячейка `t` не влияет на `y_t`.

---

## 2. Хронологическое разбиение (split)

**Принцип:** данные разбиваются по времени без перемешивания (no shuffling),
чтобы предотвратить утечку будущего в прошлое.

### Границы (config.yaml)

```
train:  [data_start,  train_end)       # train_end — исключается
val:    [train_end,    val_end)        # val_end   — исключается
test:   [val_end,      data_end]
```

- `train_end = "2023-12-31"`
- `val_end   = "2024-06-30"`

### Правила

- Разбиение строго по `DatetimeIndex` (UTC).
- Пересечения между сплитами **запрещены**.
- Порог классификации выбирается **только на validation**.
- Метрики финальной модели считаются **только на test**.

### Реализация

[`features.split_train_val_test`](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/features.py)

### Тесты

- `test_chronological_split` — train < val < test, нет пересечений.

---

## 3. Каузальные признаки (causal features)

Все временные признаки должны использовать **только данные из прошлого**
относительно момента прогноза `t`. Использование будущего запрещено.

### Допустимые операции

| Операция | Правило | Реализация |
|----------|---------|------------|
| **Lag** | `series.shift(k)`, `k >= 1` | `features.add_lag_features` |
| **Rolling count** | `shifted.rolling(window=W, closed="left")`, окно `[t-W, t)` | `features.add_rolling_alert_counts` |
| **EMA / MACD** | `series.ewm(span=W, adjust=False)` — экспоненциальное среднее по прошлым значениям | `agents.validation` |
| **Calendar** | детерминированные функции от `t` (hour, dow, month, days_since_war_start) | `features.add_calendar_features` |
| **Neighbor lag** | `neighbor_series.shift(k)`, `k >= 1` | `features.add_lag_features` с префиксом `nb_` |
| **Current state** | `current_alert_duration`, `time_since_last_alert` — вычисляются из значений ≤ t | `features.add_current_alert_duration`, `add_time_since_last_alert` |

### Запрещённые операции

- `shift(-k)` (look-ahead).
- `rolling(..., closed="right" или "both")` включая текущую ячейку для таргета.
- Любые агрегаты, использующие данные после `t`.
- Обучаемые энкодеры/скейлеры, фитящиеся на всём датасете (фитятся только на train).

### Проверка каузальности

- `validate_no_leakage.check_lag_features_not_future` — голова lag-признаков = 0 (cold start), тело совпадает с прошлыми значениями.
- `validate_no_leakage.check_target_correctness` — target вычислен без утечки.
- `validate_no_leakage.check_no_target_in_features` — целевой столбец не попал в признаки.

### Тесты

- `test_lag_features_use_past_only` — lag-признаки используют только прошлое.

---

## 4. Выбор порога классификации (threshold)

Порог выбирается **исключительно на validation** выборке. На test применяется
готовый порог без подстройки.

### Режимы (config.threshold)

| `metric` | Правило выбора |
|----------|----------------|
| `"f1"`   | порог, максимизирующий F1 на validation |
| `"recall"` | наибольший порог, при котором `recall >= min_recall` |

### Параметры

- `min_recall` — минимальный требуемый recall (по умолчанию 0.70).
- Кандидаты порогов: 201 квантиль распределения вероятностей на validation.

### Реализация

[`models.select_threshold`](file:///e:/TestTask/KSE_Agentic_Autumn2026/air-alerts-forecast/src/models.py)

### Правила

- Порог **никогда** не выбирается на test.
- При отсутствии валидных кандидатов — fallback `threshold = 0.5`.
- Каждая модель получает собственный порог, подобранный на validation.

---

## 5. Метрики оценки

Основная метрика — **PR-AUC** (Average Precision), так как классы
несбалансированы (~2.8% положительных). Дополнительно:

- ROC-AUC
- F1 (при выбранном пороге)
- Precision / Recall
- Brier score
- Calibration curve
- Lift over persistence baseline

Порог и PR-AUC на validation используются для сравнения моделей; финальные
метрики — на test.

---

## 6. Invariants (инварианты пайплайна)

1. Все lag-признаки имеют `shift(k >= 1)`.
2. Все rolling-окна используют `closed="left"` и исключают текущую ячейку.
3. Target `y_t` не зависит от значений ряда в момент `t` и ранее `t`.
4. Splits не пересекаются и упорядочены по времени.
5. Порог классификации выбирается только на validation.
6. Скейлеры/энкодеры фитятся только на train.
7. Каждый запуск сохраняет run-log с `run_id`, `config_hash`, `feature_names`, `metrics`.
