.PHONY: help setup db-up db-down db-logs backend frontend dev test lint fmt migrate revision clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

db-up: ## Start Postgres
	docker compose up -d db

db-down: ## Stop Postgres
	docker compose down

db-logs: ## Tail Postgres logs
	docker compose logs -f db

backend: ## Run the API with reload on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend: ## Run the Vite dev server on :5173
	cd frontend && npm run dev

dev: db-up ## Start Postgres, then run backend and frontend together
	@echo "Postgres up. Run 'make backend' and 'make frontend' in separate terminals."

test: ## Run backend tests
	cd backend && uv run pytest

lint: ## Lint and typecheck both sides
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	cd frontend && npm run lint && npm run typecheck

fmt: ## Auto-format both sides
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

migrate: ## Apply migrations
	cd backend && uv run alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add books"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/dist
