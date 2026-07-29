# ==========================================
# 1. BASE Build
# ==========================================
FROM python:3.11-slim as base

# Настройка окружения Python (запрет на создание .pyc файлов и буферизацию логов)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_REQUESTS_TIMEOUT=1000 \
    PIP_DEFAULT_TIMEOUT=1000 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# ==========================================
# 2. BUILDER STAGE (Установка зависимостей)
# ==========================================
FROM base as builder

# Устанавливаем системные зависимости для компиляции пакетов (например, asyncpg или confluent-kafka)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
ENV POETRY_VERSION=2.3.3
RUN pip install "poetry==$POETRY_VERSION"

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем конфигурацию Poetry
COPY pyproject.toml poetry.lock* ./

# Устанавливаем ВСЕ зависимости (prod + dev: pytest и т.п.) —
# единый образ используется и в dev, и в prod, и в CI-тестах
RUN poetry lock && poetry install --no-root

# ==========================================
# 3. RUNTIME (единый образ для dev и prod)
# ==========================================
# Один и тот же образ работает в dev и prod; поведение управляется
# переменными окружения (APP_RELOAD, APP_WORKERS, APP_HOST, APP_PORT)
FROM base as runtime

# Создаем пользователя без root-прав для безопасности (всегда, и в dev, и в prod)
RUN groupadd -r webuser && useradd -r -g webuser webuser

# Забираем ТОЛЬКО готовое окружение (без компиляторов gcc из слоя builder)
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Копируем исходный код приложения
COPY ./app ./app

# Меняем владельца файлов на безопасного пользователя
RUN chown -R webuser:webuser /app
USER webuser

# Поведение процесса задается переменными окружения:
#   APP_RELOAD=true  -> uvicorn --reload (dev, hot reload через volume mounts)
#   APP_RELOAD=false -> uvicorn --workers $APP_WORKERS (prod)
ENV APP_RELOAD=false \
    APP_WORKERS=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

CMD ["sh", "-c", "if [ \"$APP_RELOAD\" = \"true\" ]; then exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --reload; else exec uvicorn app.main:app --host \"$APP_HOST\" --port \"$APP_PORT\" --workers \"$APP_WORKERS\"; fi"]
