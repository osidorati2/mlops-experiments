-- Фиксированный набор данных для проверки sql/queries.sql. Загружать в пустую БД.
-- Ожидаемые результаты записаны в tests/test_sql_queries.py и в README.

INSERT INTO images (id, filename) VALUES
    (1, 'cat.png'),
    (2, 'dog.jpg'),
    (3, 'cat.png'),      -- то же имя файла, но другое изображение
    (4, 'broken.png'),   -- без предсказаний
    (5, 'pending.jpg');  -- без предсказаний

INSERT INTO predictions (id, image_id, class, model_version, created_at) VALUES
    (1, 1, 'cat', 'stub-v1', '2026-11-01T10:00:00+00:00'),
    (2, 2, 'dog', 'resnet-v1', '2026-11-01T10:05:00+00:00'),
    (3, 3, 'cat', 'stub-v1', '2026-11-01T10:10:00+00:00'),
    (4, 1, 'cat', 'resnet-v1', '2026-11-01T10:15:00+00:00');  -- второе предсказание для изображения 1
