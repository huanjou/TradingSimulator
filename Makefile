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

test:
	cd infra && docker compose -f docker-compose.test.yml down -v
	cd infra && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner

# Быстрый запуск тестов для ledger-writer (внутри уже работающего контейнера)
test-ledger:
	docker exec -e POSTGRES_URL="postgresql+asyncpg://admin:password@postgres-primary:5432/ledger_db" -e REDIS_URL="redis://redis:6379/0" -e KAFKA_BROKER="kafka:9092" exchange_ledger_writer poetry run pytest $(ARGS)

# Быстрый запуск тестов для api-gateway (внутри уже работающего контейнера)
test-gateway:
	docker exec -e KAFKA_BROKER="kafka:9092" -e QUERY_SERVICE_GRPC_URL="query-service:50051" exchange_api_gateway poetry run pytest $(ARGS)

# Быстрый запуск тестов для query-service (внутри уже работающего контейнера)
test-query:
	docker exec -e POSTGRES_URL="postgresql+asyncpg://admin:password@postgres-replica:5432/ledger_db" -e REDIS_URL="redis://redis:6379/0" exchange_query_service poetry run pytest $(ARGS)

# Быстрый запуск тестов для trading-engine (внутри уже работающего контейнера)
test-engine:
	docker exec -e KAFKA_BROKER="kafka:9092" exchange_trading_engine poetry run pytest $(ARGS)

seed:
	docker exec exchange_ledger_writer poetry run python -m scripts.seed

load-test:
	cd infra && docker compose -p load_test -f docker-compose.load.yml up --build --abort-on-container-exit --exit-code-from k6

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
