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

# Устанавливаем только основные зависимости (без dev)
RUN poetry lock && poetry install --no-root

# ==========================================
# 3. DEV Build
# ==========================================
FROM base as development

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем Poetry для dev-окружения
ENV POETRY_VERSION=2.3.3
RUN pip install "poetry==$POETRY_VERSION"

# Доустанавливаем инструменты для разработки (dev-зависимости из poetry)
COPY pyproject.toml poetry.lock* ./
RUN poetry lock && poetry install --no-root

WORKDIR /app
CMD ["bash", "-c", "alembic upgrade head && python main.py"]

# ==========================================
# 4. PROD build
# ==========================================
FROM base as production

# Создаем пользователя без root-прав для безопасности
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

# Запускаем скрипт записи
CMD ["bash", "-c", "alembic upgrade head && python main.py"]
