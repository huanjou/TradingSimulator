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
	cd infra && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner

load-test:
	cd infra && docker compose -f docker-compose.load.yml up --build --abort-on-container-exit --exit-code-from k6

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
	docker system prune -f

lint:
	pre-commit run --all-files

setup:
	pip install pre-commit
	pre-commit install
