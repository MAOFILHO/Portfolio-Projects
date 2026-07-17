# Built exclusively via `az acr build` (cloud-side) — no local Docker daemon required.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV RUN_MODE=azure \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 5003

CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "2", "run:app"]
