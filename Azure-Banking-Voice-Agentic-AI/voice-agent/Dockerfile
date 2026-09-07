FROM python:3.12-slim
WORKDIR /app

# One build context now (voice-agent/), so no --build-context bridging: the Phase 2.1 restructure
# (issue #17) put the app and its modules in one package, replacing the two-directory split that
# needed `docker buildx build --build-context voice-agent=...` and `COPY --from=voice-agent`.
COPY pyproject.toml .
COPY azbank_voice_agent/ ./azbank_voice_agent/
RUN pip install --no-cache-dir .

# Attribution for whatever R-04 measures against this run: the exact resolved dependency graph,
# transitive included. The `test -s` is the real gate -- a broken image must not ship, and app.py
# re-reads this file at boot as defense in depth against post-build drift.
RUN pip freeze > /app/installed-versions.txt && test -s /app/installed-versions.txt

EXPOSE 8000
CMD ["uvicorn", "azbank_voice_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
