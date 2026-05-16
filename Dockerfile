FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir .

RUN useradd --no-create-home --shell /bin/false appuser \
    && mkdir -p /app/data /app/models /app/logs \
    && chown -R appuser:appuser /app/data /app/models /app/logs

USER appuser

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/healthz')"

CMD ["gunicorn", "--bind", "0.0.0.0:80", "-w", "2", "ai_enterprise_workflow.service:app"]
