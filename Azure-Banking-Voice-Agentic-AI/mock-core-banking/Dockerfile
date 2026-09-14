FROM python:3.12-slim
WORKDIR /app

# Its own build context and its own image — docs/PLAN.md decision 9, "two deployables,
# shared-nothing". Nothing from voice-agent/ is copied in, and nothing here is copied there.
COPY pyproject.toml .
COPY azbank_core_banking/ ./azbank_core_banking/
RUN pip install --no-cache-dir .

# Same attribution discipline as the voice agent's image: the exact resolved dependency graph,
# transitive included, with `test -s` as the real gate so a broken image cannot ship.
RUN pip freeze > /app/installed-versions.txt && test -s /app/installed-versions.txt

EXPOSE 8001

# `--factory` because azbank_core_banking.app deliberately has no module-level app: importing it
# must not open a database or create a file. uvicorn calls build_app() at startup, which is where
# that side effect belongs.
CMD ["uvicorn", "azbank_core_banking.app:build_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
