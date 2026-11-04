# Image classifier service

Небольшое API для классификации изображений с историей предсказаний в SQLite.
Сейчас вместо модели работает заглушка: на любое изображение отвечает `cat` / `stub-v1`.
Описание задачи — в [service.md](service.md), прошлый эксперимент — в [experiments/lab01](experiments/lab01).

## Структура

```
app/
  main.py              сборка приложения: БД, предсказатель, сервис, роуты
  api.py               HTTP: /health, /predict, /history; доменные ошибки → коды ответа
  schemas.py           Pydantic-модели ответов
  service.py           сценарий: проверка → предсказание → сохранение
  image_validation.py  проверка, что байты декодируются как изображение (Pillow)
  predictor.py         интерфейс Predictor, заглушка StubPredictor, выбор реализации
  repository.py        весь SQL: сохранение в одной транзакции, история
  db.py                подключение к SQLite и схема таблиц
  errors.py            InvalidImageError, PredictionError, StorageError
  config.py            DB_PATH, PREDICTOR из переменных окружения
sql/
  queries.sql          три учебных запроса (JOIN, GROUP BY, LEFT JOIN)
  seed.sql             фиксированный набор данных для них
tests/                 тесты всех слоёв и SQL-запросов
```

## Установка

Нужен Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`-e` ставит проект в режиме разработки (правки кода подхватываются без переустановки),
`[dev]` добавляет pytest и httpx.

## Запуск

```bash
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DB_PATH` | `data/app.db` | файл SQLite; папка создаётся автоматически |
| `PREDICTOR` | `stub` | какую реализацию предсказателя использовать |

Примеры запросов:

```bash
curl localhost:8000/health
# {"status":"ok"}

curl -F file=@cat.png localhost:8000/predict
# {"image_id":1,"prediction_id":1,"class":"cat","model_version":"stub-v1"}

curl localhost:8000/history
# [{"prediction_id":1,"image_id":1,"filename":"cat.png","class":"cat","model_version":"stub-v1","created_at":"..."}]
```

Ответы с ошибкой:

| Ситуация | Код | Что в БД |
|---|---|---|
| пустой файл, текст, битая картинка | 400 | ничего |
| запрос без файла | 422 | ничего |
| предсказатель упал | 500 | ничего |
| ошибка записи в БД | 500 | откат обеих записей |

## Тесты

```bash
pytest
```

Тесты работают с SQLite в памяти или во временном файле и не трогают `data/app.db`.

## SQL-примеры

Запросы лежат в `sql/queries.sql`, проверяются на фиксированном наборе `sql/seed.sql`
(5 изображений, 4 предсказания; у изображений 4 и 5 предсказаний нет).
Создать отдельную демо-БД и выполнить запросы:

```bash
python -c "from app import db; db.init_schema(db.connect('demo.db'))"
sqlite3 demo.db < sql/seed.sql
sqlite3 -header -column demo.db < sql/queries.sql
```

Ожидаемый результат (он же зафиксирован в `tests/test_sql_queries.py`):

```
1. История с именами файлов (JOIN)
prediction_id  image_id  filename  class  model_version  created_at
4              1         cat.png   cat    resnet-v1      2026-11-01T10:15:00+00:00
3              3         cat.png   cat    stub-v1        2026-11-01T10:10:00+00:00
2              2         dog.jpg   dog    resnet-v1      2026-11-01T10:05:00+00:00
1              1         cat.png   cat    stub-v1        2026-11-01T10:00:00+00:00

2. Количество предсказаний по классам (GROUP BY)
class  predictions_count
cat    3
dog    1

3. Изображения без предсказаний (LEFT JOIN)
id  filename
4   broken.png
5   pending.jpg
```

Чтобы удалить демо-БД, выполните `rm demo.db`.

## Устройство

**Где заменить модель.** Новый класс с методом `predict(image) -> Prediction` добавляется
в `build_predictor` в `app/predictor.py` и выбирается через `PREDICTOR=<имя>`.
HTTP (`api.py`), сценарий (`service.py`) и SQL (`repository.py`) при этом не меняются.

**Зачем транзакция.** Изображение и предсказание пишутся вместе в `repository.save`
внутри `with conn:`. Если вставка предсказания упадёт, запись изображения откатится —
в БД не останется картинки без результата, а клиент получит 500, а не успех.

**Что тестируется с настоящей БД, а что подменено.**

| Тесты | БД | Предсказатель |
|---|---|---|
| `test_image_validation.py`, `test_predictor.py` | не нужна | заглушка |
| `test_service.py` | фейковый репозиторий | заглушка, шпион, сломанный фейк |
| `test_db.py`, `test_repository.py`, `test_sql_queries.py` | настоящая SQLite в памяти | не нужен |
| `test_api.py` | настоящая SQLite в памяти; один тест — во временном файле | заглушка или фейки |

Тест `test_predict_saves_linked_records_in_real_sqlite` читает данные через *отдельное*
соединение к файлу БД, поэтому видит только закоммиченное. Если сохранение отключить
(например, `save` вернёт выдуманные id, не записав их), API ответит 200, а этот тест упадёт.
