FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# Prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR $PYSETUP_PATH
COPY pyproject.toml poetry.lock ./

# Install ALL dependencies (prod + dev: pytest etc.) — the same image is
# used in dev, prod and CI test containers
RUN poetry lock && poetry install --no-root

WORKDIR /app
COPY . .

# Install the app
RUN poetry lock && poetry install

# Runtime (single image for dev and prod); behavior is controlled by
# APP_RELOAD / APP_WORKERS / APP_HOST / APP_PORT environment variables
FROM base as runtime

# Run as a non-root user (always, in dev and prod alike)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

#   APP_RELOAD=true  -> uvicorn --reload (dev, hot reload via volume mounts)
#   APP_RELOAD=false -> uvicorn --workers $APP_WORKERS (prod)
ENV APP_RELOAD=false \
    APP_WORKERS=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

CMD ["sh", "-c", "if [ \"$APP_RELOAD\" = \"true\" ]; then exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --reload; else exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --workers \"$APP_WORKERS\"; fi"]
