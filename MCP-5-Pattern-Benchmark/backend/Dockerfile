# The /tickets HTTP API. psycopg2-binary bundles its own libpq, so no
# build-time system deps are needed.
FROM python:3.12-slim

WORKDIR /app
COPY backend/ backend/

RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
