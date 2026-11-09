# Отчёт по лабораторной работе

---

## Цель работы

Научиться строить пайплайн, в котором LLM интерпретирует запрос на естественном языке и возвращает параметры в согласованном формате (структурированный ответ или вызов инструмента), а программа проверяет эти параметры и выполняет действие. 

Дополнительно: обработать ошибки разбора через повторные попытки, вести журнал выполнения и хранить состояние диалога вне модели.

---

## Архитектура

Пайплайн: `промпт -> LLM -> Pydantic-парсер -> поиск в SQLite -> результат`.

- LLM только извлекает параметры, SQL не пишет и к базе не обращается.
- Параметры валидируются схемой `ProductQuery` (Pydantic).
- `with_retry` обёрнут вокруг `промпт -> LLM -> парсер`, но не вокруг поиска. При ошибке разбора поиск не выполняется и не повторяется.
- Состояние диалога (часть 5) хранится в Python-переменной, а не в модели.
- Все шаги пишутся в `run_*.jsonl`, токен в журнал не попадает.

**Запуск:**

```bash
export API_TOKEN=''
python main.py init-db
python main.py part1
python main.py part2
python main.py part2-thinking
python main.py part3
python main.py part4
python main.py part5
python main.py tools
```

---

## Часть 1. Базовая цепочка LangChain

`ChatPromptTemplate` с `system` (роль + `{language}`) и `human` (`{query}`). Цепочка `prompt | llm | StrOutputParser()`.

Фактический вывод `python main.py part1`:

```
llm.invoke: AIMessage laptop
chain.invoke: str laptop
Ноутбук для учёбы, бюджет небольшой -> laptop
Смартфон с хорошей камерой          -> smartphone
Планшет для рисования               -> tablet
Двухкамерный холодильник            -> other
```

---

## Часть 2. Structured Output и Pydantic

### Схема

```python
class ProductQuery(BaseModel):
    category: Literal["laptop", "smartphone", "tablet", "other"]
    max_price: Optional[int] = Field(default=None, ge=0)
    sort_by: Literal["price_asc", "price_desc"] = "price_asc"
```

### Результаты

| № | Запрос | JSON | Результат |
|---|---|---|------|
| 1 | Найди ноутбуки дешевле 70 000 рублей | `{"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}` | ОК   |
| 2 | Покажи самые дорогие смартфоны | `{"category": "smartphone", "max_price": null, "sort_by": "price_desc"}` | ОК   |
| 3 | Хочу посмотреть планшеты | `{"category": "tablet", "max_price": null, "sort_by": "price_asc"}` | ОК   |
| 4 | Покажи ноутбуки до 50 тысяч | `{"category": "laptop", "max_price": 50000, "sort_by": "price_asc"}` | ОК   |
| 5 | Найди холодильники | `{"category": "other", "max_price": null, "sort_by": "price_asc"}` | ОК   |
| 6 | Хочу что-нибудь недорогое для учёбы | `{"category": "other", "max_price": null, "sort_by": "price_asc"}` | ОК     |
| 7 | Покажи ноутбуки, но чтобы не как у меня | `{"category": "laptop", "max_price": null, "sort_by": "price_asc"}` | ОК     |


- №6 «недорогое для учёбы»: без явной категории модель возвращает `other` - система не угадывает и сообщает о неподдерживаемой категории.
- №7 «не как у меня»: личного контекста у модели нет, возвращает `laptop, null, price_asc` - все ноутбуки, начиная с дешёвых.

### Задание 2.4 — режим размышления

| Запрос | thinking | Параметры | Время, с | input_tokens | output_tokens |
|---|---|---|---|---|---|
| Хочу что-нибудь недорогое для учёбы | False | `other, null, asc` | **0.38** | 589 | **30** |
| Хочу что-нибудь недорогое для учёбы | True | **`laptop`, null, asc** | **2.62** | 625 | **269** |
| Покажи ноутбуки, но чтобы не как у меня | False | `laptop, null, asc` | **0.34** | 590 | **31** |
| Покажи ноутбуки, но чтобы не как у меня | True | `laptop, null, asc` | **1.07** | 626 | **118** |


1. Время растёт в 3-7 раз, output_tokens в 4-9 раз
2. На «недорогое для учёбы» режимы дают разный результат: без размышления `other`, с размышлением `laptop`.

---

## Часть 3. Интеграция со SQLite

### Каталог

18 товаров: 6 ноутбуков, 6 смартфонов, 6 планшетов. Таблица `products` с ограничениями

### Поиск

`search_products(ProductQuery)`:

- при `category == "other"` возвращает `unsupported_category` до SQL;
- параметризованный SQL: `WHERE category = ? AND price <= ?`;
- сортировка из белого списка `{"price_asc": "ASC", "price_desc": "DESC"}`.

### Задание 3.3 - сравнительная таблица

| № | Запрос | Параметры | Найдено | Статус |
|---|---|---|---|---|
| 1 | Найди ноутбуки дешевле 70 000 | laptop, 70000, asc | IdeaPad 3 (54 990), HP 15s (62 990), VivoBook 15 (69 990) — **3** | ok |
| 2 | Покажи самые дорогие смартфоны | smartphone, null, desc | iPhone 15 (89 990), Galaxy S23 (69 990), Pixel 7a (49 990), Realme 11 Pro (27 990), Galaxy A25 (24 990), Redmi Note 13 (19 990) — **6** | ok |
| 3 | Хочу посмотреть планшеты | tablet, null, asc | Digma (10 990), Tab A9 (16 990), Redmi Pad SE (19 990), Lenovo Tab M10 (22 990), MatePad 11 (34 990), iPad 10 (44 990) — **6** |
| 4 | Покажи ноутбуки до 50 тысяч | laptop, 50000, asc | — | **empty** |
| 5 | Найди холодильники | other | — | **unsupported_category** |
| 6 | Хочу что-нибудь недорогое для учёбы | other | — | unsupported_category |
| 7 | Покажи ноутбуки, но чтобы не как у меня | laptop, null, asc | все **6** ноутбуков | ok |
| 8 | Смартфоны дешевле 30 тысяч | smartphone, 30000, asc | Redmi Note 13 (19 990), Galaxy A25 (24 990), Realme 11 Pro (27 990) — **3** | ok |
| 9 | Самые дорогие планшеты | tablet, null, desc | iPad 10 (44 990), MatePad 11 (34 990), Lenovo Tab M10 (22 990), Redmi Pad SE (19 990), Tab A9 (16 990), Digma (10 990) — **6** | ok |
| 10 | Ноутбуки до 90 тысяч | laptop, 90000, asc | IdeaPad 3 (54 990), HP 15s (62 990), VivoBook 15 (69 990), Aspire 5 (74 990), ThinkPad E14 (89 990) — **5** | ok |


### Сравнение с ответом LLM без базы

| Запрос | Ответ LLM без базы | Фактический результат SQLite |
|---|---|---|
| Какие ноутбуки дешевле 70 000 рублей есть в каталоге? | Модель генерирует правдоподобные названия и цены, которые могут не совпадать с каталогом | Строго: IdeaPad 3 54 990, HP 15s 62 990, VivoBook 15 69 990 |
| Какие смартфоны самые дорогие? | Может назвать флагманы, отсутствующие в каталоге | iPhone 15 89 990, Galaxy S23 69 990 |
| Какие планшеты дешевле 20 000 рублей? | Придумает модели и цены | Digma 10 990, Tab A9 16 990, Redmi Pad SE 19 990 |

**Вывод:** LLM без базы не может ответить - она не знает содержимого каталога и генерирует правдоподобный, но не проверяемый текст. Факты берутся только из SQLite.

### Задание 3.4 — поиск как инструмент

Фактический вывод `python main.py tools` для 5 запросов:

| Запрос | `tool_calls[0].args` | `validated_args` | Результат |
|---|---|-------------|---|
| Найди ноутбуки дешевле 70 000 | `{laptop, 70000, price_asc}` | ОК          | 3 товара |
| Покажи самые дорогие смартфоны | `{smartphone, price_desc}` → дополнен `max_price=null` | ОК            | 6 товаров |
| Хочу посмотреть планшеты | `{tablet}` → дополнен | ОК            | 6 товаров |
| Покажи ноутбуки до 50 тысяч | `{laptop, 50000, price_asc}` | ОК            | empty |
| Найди холодильники | `{other}` + текст-обоснование | ОК            | unsupported_category |

**Наблюдения:**
1. `model_content` у большинства запросов пустой - модель сразу вызывает инструмент.
2. Аргументы, не указанные явно, дополняются дефолтами при `ProductQuery.model_validate(args)`.
3. Поиск выполняется только после `model_validate`.

---

## Часть 4. Retry и журнал

### Анализ ошибок парсера

Фактический вывод `python main.py part4`:

| Ответ | Тип исключения | `cause` | Этап |
|---|---|---|---|
| `{"category": "laptop", "max_price": 70000` | — (не упало) | — | — |
| `{"category": "fridge", ...}` | `OutputParserException` | `ValidationError` (Literal) | валидация Pydantic |
| `{"category": "laptop", "max_price": -100, ...}` | `OutputParserException` | `ValidationError` (ge=0) | ограничение |
| `{"category": "laptop", "max_price": "много", ...}` | `OutputParserException` | `ValidationError` | приведение типа |

**Про `malformed_json`:** `PydanticOutputParser` использует `parse_json_markdown`, который прощает часть синтаксических ошибок. Незакрытый JSON восстанавливается как валидный, `sort_by` подставляется по умолчанию. Для гарантированной ошибки нужны нарушения схемы — `Literal` и `ge`.

### Повторные попытки

```python
generation.with_retry(
    retry_if_exception_type=(OutputParserException, ValidationError),
    stop_after_attempt=3,
    wait_exponential_jitter=False,
)
```

- Максимум 3 попытки, включая первоначальную.
- Повтор только генерации и парсинга.
- Поиск вне `with_retry`.

### Журнал

Фрагмент `run_fake_retry_success.jsonl` (сценарий «ошибка → успех»):

```json
{"event": "request_start", "query": "Ноутбуки до 70 тысяч"}
{"event": "llm_start", "attempt": 1, "max_attempts": 3}
{"event": "llm_end", "attempt": 1, "content_len": 43}
{"event": "parse_error", "attempt": 1, "error_type": "OutputParserException", "cause_type": "ValidationError"}
{"event": "llm_start", "attempt": 2, "max_attempts": 3}
{"event": "llm_end", "attempt": 2, "content_len": 66}
{"event": "parse_ok", "attempt": 2, "params": {"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}}
{"event": "params_validated", "params": {"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}}
{"event": "search_start", "params": {"category": "laptop", "max_price": 70000, "sort_by": "price_asc"}}
{"event": "search_done", "status": "ok", "found": 3, "search_call": 1}
{"event": "request_done", "query": "Ноутбуки до 70 тысяч", "found": 3}
```

### Воспроизводимые тесты

Фактический вывод:

```
retry success: attempts=2, search_calls=1
no retry: search_calls=0
all fail: attempts=3, search_calls=0
```

| Тест | `responses` | `max_attempts` | `attempts` | `search_calls` |
|---|---|---|---|---|
| `test_retry_success` | невалидный, валидный | 3 | **2** | **1** |
| `test_no_retry_fails` | невалидный, валидный | **1** | 1 | **0** |
| `test_all_attempts_fail` | 3 разных невалидных | 3 | **3** | **0** |

---

## Часть 5. Уточняющие запросы

### Задание 5.2 — StatefulAgent vs HistoryAgent

**StatefulAgent** хранит `self.state: ProductQuery | None` в Python-переменной, в промпт передаётся JSON текущих параметров + новая реплика.

**HistoryAgent** хранит `self.history: list[dict]`, в промпт передаётся вся история диалога.

### Результаты

**STATE:**

| Шаг | Реплика | Параметры | Найдено | input_tokens |
|---|---|---|---|---|
| 1 | Покажи ноутбуки до 80 тысяч | `laptop, 80000, asc` | 4 | 517 |
| 2 | А сначала дорогие? | `laptop, 80000, desc` | 4 | 525 |
| 3 | А что есть среди смартфонов? | **`smartphone`**, 80000, desc | 5 | 531 |

 Все три шага сохраняют нужные параметры.

**HISTORY:**

| Шаг | Реплика | Параметры | Найдено | input_tokens |
|---|---|---|---|---|
| 1 | Покажи ноутбуки до 80 тысяч | `laptop, 80000, asc` | 4 | 470 |
| 2 | А сначала дорогие? | `laptop, 80000, desc` | 4 | 495 |
| 3 | А что есть среди смартфонов? | `smartphone, null, asc` | 6 | 538 |

На шаге 3 модель сбросила `max_price` и `sort_by`, хотя пользователь их не отменял. Найдено 6 смартфонов вместо ожидаемых 5 (iPhone за 89 990 должен быть отсечён по `max_price=80000`).

### Сравнение

| Аспект | STATE               | HISTORY             |
|---|---------------------|---------------------|
| Корректность на шаге 3 | параметры сохранены | сброшены на дефолты |
| input_tokens на шаге 1 | 517                 | 470                 |
| input_tokens на шаге 3 | 531 (+14)           | 538 (+68)           |
| Устойчивость к длине диалога | не зависит          | падает              |

**Вывод:** state-вариант передаёт только компактный JSON текущих параметров - токены растут медленно, модель не путается. History передаёт все реплики из-за чего токены растут быстрее, а на шаге 3 модель сбросила ограничения

---

## Анализ ошибок

### `429 RateLimitError` при `chain.batch`

**Причина:** `chain.batch(queries)` по умолчанию отправляет все запросы параллельно. Сервер разрешает максимум 3 параллельных запроса. Четыре запроса в `demo_batch` → 4 потока → 429.

**Решение:** `chain.batch(queries, config={"max_concurrency": 2})`.

### `OutputParserException` не возникает для `malformed_json`

**Симптом:** ожидалось `OutputParserException`, получено «неожиданно валидно».

**Причина:** `PydanticOutputParser` использует `parse_json_markdown`, который восстанавливает часть незакрытых JSON. `{"category": "laptop", "max_price": 70000` парсится как валидный объект, `sort_by` подставляется по умолчанию.

**Решение:** для гарантированной ошибки использовать нарушение схемы (`"category": "fridge"`, `"max_price": -100`, `"max_price": "много"`).

---

## Выводы

1. LLM хорошо извлекает параметры, но не должна быть источником фактов о каталоге.

2. Pydantic-схема обеспечивает границу между текстом модели и SQL.

3. Журнал фиксирует порядок событий. Поиск вызывается только после валидации

4. Хранение состояния вне модели дешевле по токенам и надёжнее.

5. Режим размышления (`enable_thinking=True`) увеличивает время в 3-7 раз и output_tokens в 4-9 раз.

---

## артефакты запуска

| Файл | Содержимое                         |
|---|------------------------------------|
| `catalog.db` | SQLite-база                        |
| `run_part2.jsonl` | журнал части 2                     |
| `run_part2_thinking.jsonl` | журнал части 2.4                   |
| `run_part3.jsonl` | журнал части 3.3                   |
| `run_part5.jsonl` | журнал части 5                     |
| `run_fake_retry_success.jsonl` | сценарий «ошибка -> успех»         |
| `run_fake_no_retry.jsonl` | сценарий без retry                 |
| `run_fake_all_fail.jsonl` | сценарий «все попытки провалились» |
| `run_tools.jsonl` | журнал части 3.4                   |
