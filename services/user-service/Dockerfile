FROM python:3.11-slim as requirements-stage
WORKDIR /tmp
RUN pip install poetry poetry-plugin-export
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.11-slim
WORKDIR /app
COPY --from=requirements-stage /tmp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY ./app /app/app

# Since user-service shares the users table with ledger-writer, we assume
# migrations are handled globally or tables are created on startup (or via alembic).
# For MVP, we will rely on ledger-writer or query-service creating the users table,
# but it's best to create it if it doesn't exist.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
