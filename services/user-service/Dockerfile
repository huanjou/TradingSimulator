FROM python:3.11-slim as requirements-stage
WORKDIR /tmp
RUN pip install poetry poetry-plugin-export
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes
# Separate export with dev tools (pytest & co) for the development/test image
RUN poetry export -f requirements.txt --with dev --output requirements-dev.txt --without-hashes

# Common base with dependencies and application code
FROM python:3.11-slim as base
WORKDIR /app
COPY --from=requirements-stage /tmp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./app /app/app
COPY ./alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Development image (runs as root for convenience with bind mounts)
FROM base as development
COPY --from=requirements-stage /tmp/requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Production image (non-root, multiple workers)
FROM base as production
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]
