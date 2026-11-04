-- Написать три SQL-запроса:
--          история с именами файлов через JOIN;
--          количество предсказаний по классам через GROUP BY;
--          изображения без предсказаний через LEFT JOIN.
-- Проверить на небольшом фиксированном наборе данных.


-- 1. История предсказаний с именами файлов (JOIN), новые сверху.
SELECT predictions.id AS prediction_id, predictions.image_id, images.filename,
predictions.class, predictions.model_version, predictions.created_at
FROM predictions
JOIN images ON predictions.image_id = images.id
ORDER BY predictions.created_at DESC, predictions.id DESC;

-- 2. Количество предсказаний по классам (GROUP BY).
SELECT predictions.class, COUNT(*) AS predictions_count
FROM predictions
GROUP BY predictions.class
ORDER BY predictions.class;

-- 3. Изображения без предсказаний (LEFT JOIN).
SELECT images.id, images.filename
FROM images
LEFT JOIN predictions ON images.id = predictions.image_id
WHERE predictions.id IS NULL
ORDER BY images.id;
