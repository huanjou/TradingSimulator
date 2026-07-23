.PHONY: up down build prod-up prod-build logs clean lint setup test

# ==========================================
# DEVELOPMENT
# ==========================================
up:
	cd infra && docker compose up -d

down:
	cd infra && docker compose down

build:
	cd infra && docker compose up --build -d

logs:
	cd infra && docker compose logs -f

test: test-clean
	cd infra && docker compose -p test_env -f docker-compose.test.yml up --build -d postgres-primary postgres-replica redis test-kafka trading-engine ledger-writer query-service market-data cache-writer
	python -c "import time; time.sleep(10)"
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-api-gateway || (cd .. && make test-clean && exit 1)
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-trading-engine || (cd .. && make test-clean && exit 1)
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-ledger-writer || (cd .. && make test-clean && exit 1)
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-query-service || (cd .. && make test-clean && exit 1)
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-market-data || (cd .. && make test-clean && exit 1)
	cd infra && docker compose -p test_env -f docker-compose.test.yml run --build --rm test-cache-writer || (cd .. && make test-clean && exit 1)
	make test-clean

test-e2e:
	pytest tests/e2e -v -s

test-clean:
	cd infra && docker compose -p test_env -f docker-compose.test.yml down -v

# Быстрый запуск тестов для ledger-writer (внутри уже работающего контейнера)
test-ledger:
	docker exec -e POSTGRES_URL="postgresql+asyncpg://admin:password@postgres-primary:5432/ledger_db" -e REDIS_URL="redis://redis:6379/0" -e KAFKA_BROKER="kafka:9092" exchange_ledger_writer pytest $(ARGS)

# Быстрый запуск тестов для api-gateway (внутри уже работающего контейнера)
test-gateway:
	docker exec -e KAFKA_BROKER="kafka:9092" -e QUERY_SERVICE_GRPC_URL="query-service:50051" exchange_api_gateway pytest $(ARGS)

# Быстрый запуск тестов для query-service (внутри уже работающего контейнера)
test-query:
	docker exec -e POSTGRES_URL="postgresql+asyncpg://admin:password@postgres-replica:5432/ledger_db" -e REDIS_URL="redis://redis:6379/0" exchange_query_service pytest $(ARGS)

# Быстрый запуск тестов для trading-engine (внутри уже работающего контейнера)
test-engine:
	docker exec -e KAFKA_BROKER="kafka:9092" exchange_trading_engine pytest $(ARGS)

# Быстрый запуск тестов для cache-writer (внутри уже работающего контейнера)
test-cache:
	docker exec -e KAFKA_BROKER="kafka:9092" -e REDIS_URL="redis://redis:6379/0" exchange_cache_writer pytest $(ARGS)


load-test:
	cd infra && docker compose -p load_test -f docker-compose.load.yml up --build --abort-on-container-exit --exit-code-from k6

load-test-local:
	docker run --rm -v "$(CURDIR)/tests/load:/scripts" --network infra_exchange_net -e API_URL=http://exchange_api_gateway:8000/api/v1/orders grafana/k6 run /scripts/orders.js

limiter-test:
	cd infra && docker compose -p limiter_test -f docker-compose.limiter.yml up --build --abort-on-container-exit --exit-code-from k6

benchmark-engine-core:
	docker exec exchange_trading_engine python -m tests.benchmark_core

benchmark-engine-kafka:
	docker exec -e KAFKA_BROKER="kafka:9092" exchange_trading_engine python -m tests.benchmark_kafka

benchmark-ledger:
	docker exec -e KAFKA_BROKER="kafka:9092" -e POSTGRES_URL="postgresql+asyncpg://admin:password@postgres-primary:5432/ledger_db" exchange_ledger_writer python -m tests.benchmark_db

# ==========================================
# PRODUCTION
# ==========================================
prod-up:
	cd infra && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-build:
	cd infra && docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d

# ==========================================
# UTILITIES
# ==========================================
clean:
	cd infra && docker compose down -v
	cd infra && docker compose -f docker-compose.test.yml down -v
	cd infra && docker compose -f docker-compose.load.yml down -v
	docker system prune -f

generate-protos:
	cd services/api-gateway && poetry run python -m grpc_tools.protoc -I../../protos --python_out=./app/grpc_stubs --grpc_python_out=./app/grpc_stubs ../../protos/orders.proto
	cd services/query-service && poetry run python -m grpc_tools.protoc -I../../protos --python_out=./app/grpc_stubs --grpc_python_out=./app/grpc_stubs ../../protos/orders.proto
	cd services/api-gateway && poetry run python -c "content=open('app/grpc_stubs/orders_pb2_grpc.py').read(); open('app/grpc_stubs/orders_pb2_grpc.py', 'w').write(content.replace('import orders_pb2 as orders__pb2', 'from . import orders_pb2 as orders__pb2'))"
	cd services/query-service && poetry run python -c "content=open('app/grpc_stubs/orders_pb2_grpc.py').read(); open('app/grpc_stubs/orders_pb2_grpc.py', 'w').write(content.replace('import orders_pb2 as orders__pb2', 'from . import orders_pb2 as orders__pb2'))"

lint:
	pre-commit run --all-files

setup:
	pip install pre-commit
	pre-commit install
