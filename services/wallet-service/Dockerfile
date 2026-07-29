# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

RUN pip install --no-cache-dir poetry

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
# Install ALL dependencies (prod + dev: pytest etc.) — the same image is
# used in dev, prod and CI test containers
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Stage 2: Runtime (single image for dev and prod); behavior is controlled
# by APP_RELOAD / APP_WORKERS / APP_HOST / APP_PORT environment variables
FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

# Run as a non-root user (always, in dev and prod alike)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

#   APP_RELOAD=true  -> uvicorn --reload (dev, hot reload via volume mounts)
#   APP_RELOAD=false -> uvicorn --workers $APP_WORKERS (prod)
ENV APP_RELOAD=false \
    APP_WORKERS=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

CMD ["sh", "-c", "if [ \"$APP_RELOAD\" = \"true\" ]; then exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --reload; else exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --workers \"$APP_WORKERS\"; fi"]
