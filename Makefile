# PrintBar — Developer Makefile
# Provides shortcuts for all common development tasks.
# Run `make help` to see all available commands.

.PHONY: help dev build test lint migrate seed clean install backend-shell

BACKEND_DIR := apps/backend
KIOSK_DIR   := apps/kiosk

##@ General

help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

dev: ## Start the full development stack (Docker Compose)
	docker compose up --build

dev-backend: ## Start only the backend service
	docker compose up backend postgres redis --build

dev-bg: ## Start the development stack in the background
	docker compose up -d --build

stop: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose down && docker compose up -d --build

##@ Installation

install: ## Install backend development dependencies (local)
	cd $(BACKEND_DIR) && pip install -r requirements/dev.txt

install-frontend: ## Install frontend dependencies
	bun install

##@ Testing

test: ## Run all backend tests
	cd $(BACKEND_DIR) && pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=85

test-unit: ## Run unit tests only
	cd $(BACKEND_DIR) && pytest tests/ -v -m unit

test-integration: ## Run integration tests only
	cd $(BACKEND_DIR) && pytest tests/ -v -m integration

test-health: ## Run health endpoint tests only
	cd $(BACKEND_DIR) && pytest tests/test_health.py -v

test-payment: ## Run payment tests
	cd $(BACKEND_DIR) && pytest tests/test_payment.py -v

test-upload: ## Run upload tests
	cd $(BACKEND_DIR) && pytest tests/test_upload.py -v

test-ws: ## Run WebSocket tests
	cd $(BACKEND_DIR) && pytest tests/test_websocket.py -v

##@ Code Quality

lint: ## Run ruff linter on backend
	cd $(BACKEND_DIR) && ruff check app/ tests/

lint-fix: ## Run ruff with auto-fix
	cd $(BACKEND_DIR) && ruff check --fix app/ tests/

typecheck: ## Run mypy type checker
	cd $(BACKEND_DIR) && mypy app/

format: ## Format backend code with ruff
	cd $(BACKEND_DIR) && ruff format app/ tests/

##@ Database

migrate: ## Run all pending Alembic migrations
	cd $(BACKEND_DIR) && alembic upgrade head

migrate-dry: ## Show SQL for pending migrations (no execution)
	cd $(BACKEND_DIR) && alembic upgrade head --sql

rollback: ## Roll back the last migration
	cd $(BACKEND_DIR) && alembic downgrade -1

rollback-all: ## Roll back all migrations (WARNING: destroys data)
	cd $(BACKEND_DIR) && alembic downgrade base

new-migration: ## Create a new migration file. Usage: make new-migration MSG="add users table"
	cd $(BACKEND_DIR) && alembic revision --autogenerate -m "$(MSG)"

seed: ## Seed the database with initial pricing data
	cd $(BACKEND_DIR) && python -m scripts.seed

##@ Docker

build: ## Build all Docker images
	docker compose build

build-backend: ## Build only the backend image
	docker compose build backend

push: ## Push Docker images to registry (requires REGISTRY env var)
	docker compose push

##@ Logs

logs: ## Tail all service logs
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

logs-nginx: ## Tail nginx logs
	docker compose logs -f nginx

##@ Shell Access

backend-shell: ## Open a shell inside the backend container
	docker compose exec backend /bin/bash

postgres-shell: ## Open psql inside the postgres container
	docker compose exec postgres psql -U printbar printbar_dev

redis-shell: ## Open redis-cli inside the redis container
	docker compose exec redis redis-cli

##@ Cleanup

clean: ## Remove all containers, volumes, and build cache
	docker compose down -v --remove-orphans
	docker system prune -f

clean-logs: ## Clear application log files
	find . -name "*.log" -delete

clean-pycache: ## Remove Python cache files
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
