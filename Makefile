.PHONY: help dev up down build test lint format clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	docker compose up --build -d

down: ## Stop all services
	docker compose down

logs: ## Tail all logs
	docker compose logs -f

backend-logs: ## Tail backend logs
	docker compose logs -f backend

test: ## Run all tests
	docker compose exec backend pytest tests/ -v

lint: ## Run linter
	ruff check .

format: ## Format code
	ruff format .

clean: ## Clean up Docker volumes
	docker compose down -v --remove-orphans

reset: ## Reset simulator and database
	docker compose exec backend python -m scripts.reset_db

shell: ## Open backend shell
	docker compose exec backend python -c "import IPython; IPython.start_ipython()"
