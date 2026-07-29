FROM python:3.12-slim

WORKDIR /app

# Install the shared surveil_core package first (models, analyzer, alert
# rules, storage/notify clients) so both the backend and the Function image
# build from one source of truth — see shared/README.md.
COPY shared /app/shared
RUN pip install --no-cache-dir /app/shared

COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt

COPY backend/app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
