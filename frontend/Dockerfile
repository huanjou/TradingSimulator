# ==========================================================================
# NOTE: Фронтенд — ЕДИНСТВЕННЫЙ сервис с раздельными dev/prod таргетами.
#
# Все Python-сервисы собираются в ОДИН образ (поведение управляется
# переменными APP_RELOAD/APP_WORKERS), но для Next.js это невозможно:
#   * dev  (`npm run dev`)   — dev-сервер с HMR, компиляцией на лету
#     и полным node_modules;
#   * prod (`node server.js`) — заранее собранный standalone-бандл
#     без dev-сервера вообще.
# Это два принципиально разных рантайма, а не один процесс с разными
# флагами, поэтому здесь сохраняются два таргета:
#   development — используется в infra/docker-compose.yml
#   production  — используется в infra/docker-compose.prod.yml
# ==========================================================================

# ==========================================
# 1. BASE build
# ==========================================
FROM node:20-alpine AS base

# Устанавливаем зависимости, необходимые для некоторых Node.js пакетов (например, для оптимизации изображений)
RUN apk add --no-cache libc6-compat
WORKDIR /app

# ==========================================
# 2. Dependencies
# ==========================================
FROM base AS deps
# Копируем только файлы конфигурации пакетов для кэширования этого слоя
COPY package.json package-lock.json* ./
# Чистая установка зависимостей
RUN npm install

# ==========================================
# 3. DEV Build
# ==========================================
FROM base AS development
WORKDIR /app
COPY package.json package-lock.json* ./
COPY --from=deps /app/node_modules ./node_modules
CMD ["npm", "run", "dev"]

# ==========================================
# 4. BUILDER STAGE
# ==========================================
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Важно: В next.config.js должна быть включена опция output: 'standalone'
RUN npm run build

# ==========================================
# 5. PROD Build
# ==========================================
FROM base AS production
WORKDIR /app

ENV NODE_ENV=production
# Отключаем телеметрию Next.js
ENV NEXT_TELEMETRY_DISABLED=1

# Создаем безопасного non-root пользователя (Staff Best Practice)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Копируем только необходимые файлы из builder
COPY --from=builder /app/public ./public

# Автоматически создаем папку для кэша и даем права
RUN mkdir .next && chown nextjs:nodejs .next

# Standalone билд Next.js создает минимально необходимую копию node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# В Standalone режиме мы запускаем server.js, а не npm start
CMD ["node", "server.js"]
