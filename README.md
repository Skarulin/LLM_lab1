# Лабораторная 1

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export API_TOKEN=""

python main.py init-db
```

## Команды

```bash
python main.py part1           # базовая цепочка + batch
python main.py part2           # structured output
python main.py part2-thinking  # сравнение thinking
python main.py part3           # SQLite + 10 запросов
python main.py part4           # retry
python main.py part5           # state vs history
python main.py tools           # поиск как инструмент
```

## Файлы

## Файлы

| Файл | Что внутри                            |
|---|---------------------------------------|
| `main.py` | вызов частей                          |
| `config.py` | токен, URL сервера, имя модели        |
| `schemas.py` | схема `ProductQuery` (Pydantic)       |
| `db.py` | каталог товаров и `init_db()`         |
| `search.py` |SQL-поиск                              |
| `journal.py` |журналы                                |
| `llm.py` |создание клиента `ChatOpenAI`|
| `basic_chain.py` | часть 1                               |
| `agent.py` | части 2, 3.3, 4.2                     |
| `tool_calling.py` | часть 3.4                             |
| `dialog.py` | часть 5                               |
| `retry_tests.py` | часть 4.4                 |
| `requirements.txt` | зависимости                           |
| `REPORT.md` | отчёт                                 |