.PHONY: up down build prod-up prod-build logs clean lint setup

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
