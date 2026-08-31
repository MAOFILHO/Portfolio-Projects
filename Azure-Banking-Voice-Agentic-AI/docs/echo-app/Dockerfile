FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
COPY --from=voice-agent requirements.txt voice-agent-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r voice-agent-requirements.txt
RUN pip freeze > /app/installed-versions.txt && test -s /app/installed-versions.txt
COPY app.py .
COPY --from=voice-agent bridge.py accounts.py ./voice-agent/
ENV PYTHONPATH=/app/voice-agent
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
