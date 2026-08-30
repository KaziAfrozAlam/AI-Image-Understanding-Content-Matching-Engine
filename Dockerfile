FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for a little extra hygiene.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command runs the API (the in-process worker can also be enabled via
# WORKER_ENABLED). The separate `worker` service runs the job runner instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
