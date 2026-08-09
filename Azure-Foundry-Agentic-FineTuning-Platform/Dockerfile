# Backend image — FastAPI + LangGraph + MCP. Runs in DEMO_MODE=mock by
# default (see docker-compose.yml), so `docker run` needs zero Azure
# credentials to produce a working demo.
FROM python:3.12-slim AS backend

WORKDIR /app

# System deps: none required at runtime (pure-Python stack); curl only for
# the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY mcp_servers/ mcp_servers/
COPY data/ data/
COPY pyproject.toml .

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    DEMO_MODE=mock

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
