FROM python:3.11-slim as requirements-stage
WORKDIR /tmp
RUN pip install poetry poetry-plugin-export
COPY ./pyproject.toml ./poetry.lock* /tmp/
# Export prod + dev dependencies (pytest & co) — the same image is used in
# dev, prod and CI test containers
RUN poetry export -f requirements.txt --with dev --output requirements.txt --without-hashes

# Runtime (single image for dev and prod); behavior is controlled by
# APP_RELOAD / APP_WORKERS / APP_HOST / APP_PORT environment variables
FROM python:3.11-slim as runtime
WORKDIR /app
COPY --from=requirements-stage /tmp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./app /app/app
COPY ./alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Run as a non-root user (always, in dev and prod alike)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

#   APP_RELOAD=true  -> uvicorn --reload (dev, hot reload via volume mounts)
#   APP_RELOAD=false -> uvicorn --workers $APP_WORKERS (prod)
ENV APP_RELOAD=false \
    APP_WORKERS=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

CMD ["sh", "-c", "alembic upgrade head && if [ \"$APP_RELOAD\" = \"true\" ]; then exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --reload; else exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --workers \"$APP_WORKERS\"; fi"]
