FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GYM_DB_PATH=/data/gym.db \
    GYM_XLSX_PATH=/seed/Exercises_2.xlsx \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persisted DB lives in /data; the seed spreadsheet is mounted at /seed.
VOLUME ["/data"]
EXPOSE 8000

# gunicorn imports app:app, which runs bootstrap() (init + seed) on startup.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "app:app"]
