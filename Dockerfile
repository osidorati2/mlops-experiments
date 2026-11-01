FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORKERS=1 \
    MODEL_SIZE_MIB=128 \
    WORK_ROUNDS=2000

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Непривилегированный пользователь
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# exec — чтобы uvicorn стал PID 1 и корректно получал SIGTERM.
# Число процессов задаётся переменной WORKERS (1, 2, 4).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers \"$WORKERS\" --no-access-log"]
