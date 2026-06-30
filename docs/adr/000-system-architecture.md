# ADR 000: Архитектура системы

**Дата:** 2026-06-23
**Автор:** Huan Jou

## Макро-архитектура: Симулятор биржевых торгов (High-Load Pet Project)

Стек технологий:

- Next.js (React)
- FastAPI (Python)
- Apache Kafka
- PostgreSQL
- Redis

**Архитектурный стиль: Microservices, Event-Driven, CQRS.**

## 1. Описание продукта

Проект представляет собой симулятор биржевых торгов.

## 2. Акторы (Внешние сущности)

- Трейдер (Пользователь): Авторизуется в системе, просматривает графики, выставляет ордера (Market, Limit, TP/SL), следит за портфелем.

- Провайдер рыночных данных (Binance WS/Finhub): Внешний источник истины для котировок в реальном времени. Поставляет поток цен для исполнения ордеров.

## 3. Архитектура Контейнеров (C4 Level 2)

Система разбита на независимые микросервисы. Каждый сервис выполняет строго одну бизнес-задачу (Single Responsibility) и может масштабироваться отдельно.

```mermaid
graph TD
    %% Пользовательский уровень
    User((Трейдер)) -->|HTTPS / WSS| WebApp[Frontend App <br/> Next.js / Tailwind]

    %% Шлюзы
    WebApp -->|REST API <br/> HTTP| Gateway[API Gateway <br/> FastAPI]
    WebApp -.->|WebSocket <br/> Updates| WSServer[Notification WS <br/> FastAPI / Redis PubSub]

    %% Брокер сообщений
    Gateway -->|Produce: OrderPlaced| KafkaIn[(Kafka <br/> orders.inbound)]

    %% Ядро
    KafkaIn -->|Consume Group: Matcher| Engine{{Matching Engine <br/> Python In-Memory}}
    Oracle((Binance API)) -->|WS Price Stream| Engine
    Engine -->|Produce: OrderExecuted| KafkaOut[(Kafka <br/> trades.outbound)]

    %% Ledger & База Данных (Параллельное чтение)
    KafkaIn -->|Consume Group: Ledger_In| Ledger[Ledger Service <br/> Python DB Writer]
    KafkaOut -->|Consume Group: Ledger_Out| Ledger
    Ledger -->|SQL ACID Transactions| DB[(PostgreSQL)]

    %% Уведомления фронтенда
    Ledger -->|Publish Event| RedisPubSub[(Redis <br/> Pub/Sub)]
    RedisPubSub -->|Subscribe| WSServer

    %% Оформление
    classDef frontend fill:#3178c6,stroke:#00f2fe,stroke-width:2px,color:#fff;
    classDef api fill:#4facfe,stroke:#00f2fe,stroke-width:2px,color:#fff;
    classDef kafka fill:#a18cd1,stroke:#fbc2eb,stroke-width:2px,color:#fff;
    classDef core fill:#f6d365,stroke:#fda085,stroke-width:2px,color:#333;
    classDef db fill:#43e97b,stroke:#38f9d7,stroke-width:2px,color:#333;

    class WebApp frontend;
    class Gateway,WSServer api;
    class KafkaIn,KafkaOut kafka;
    class Engine core;
    class DB,Ledger db;
```

## 3.1. Описание микросервисов

- Frontend App (Next.js): SPA приложение. Отображает графики (TradingView Lightweight Charts), форму создания ордера, стакан (опционально) и историю сделок.

- API Gateway (FastAPI): Единая точка входа для всех REST запросов. Занимается авторизацией (JWT), валидацией тела запроса и проверкой бизнес-правил. Не пишет в PostgreSQL. Отправляет валидные команды (OrderPlaced) в Kafka.

- Matching Engine (Python Worker): Stateful-сервис. Не имеет REST API. Хранит отложенные ордера в памяти (Heaps). Слушает поток котировок Binance и поток новых заявок из Kafka.Генерирует события OrderExecuted.

- Ledger Service (Python Worker): Отвечает за целостность данных в БД (PostgreSQL). Параллельно слушает Kafka orders.inbound (чтобы записать ордер со статусом PENDING) и trades.outbound (чтобы перевести статус в EXECUTED и обновить балансы пользователя).

- Notification WS Server (FastAPI): Держит тысячи открытых WebSocket соединений с фронтендом. Когда Ledger Service обновляет базу, он кидает легковесный ивент в Redis Pub/Sub, который WS Server транслирует конкретному юзеру на фронтенд ("Ордер исполнен").

# 4. Отказаустойчивость

1. При падении торгового ядра, оно востонавливает свое состояние из журнала kafka
2. Состояние бд при падении также будет восстановленно из журнала kafka
