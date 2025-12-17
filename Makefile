.PHONY: help install dev test lint format clean docker-up docker-down docker-logs monitor start api ui

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with uv
	uv sync

install-dev:  ## Install with dev dependencies with uv
	uv sync --extra dev

start:  ## Start API + UI
	./start.py

api:  ## Start API only (port 8765)
	uv run uvicorn api.main:app --host 0.0.0.0 --port 8765 --reload

ui:  ## Start UI only (port 5173)
	cd ui && npm run dev

docker-up:  ## Start all Docker services
	docker-compose up -d
	@echo "✅ Services starting..."
	@echo "📊 Grafana: http://localhost:3000"
	@echo "📈 Prometheus: http://localhost:9090"
	@echo "🔍 Jaeger: http://localhost:16686"

docker-down:  ## Stop all Docker services
	docker-compose down

docker-restart:  ## Restart all Docker services
	docker-compose restart

docker-logs:  ## Follow Docker logs
	docker-compose logs -f

docker-clean:  ## Remove all Docker volumes and data
	docker-compose down -v
	rm -rf data/*

test:  ## Run tests
	uv run pytest -v

test-cov:  ## Run tests with coverage
	uv run pytest --cov=services --cov=providers --cov-report=html --cov-report=term

lint:  ## Run linter
	uv run ruff check .

format:  ## Format code
	uv run ruff format .

typecheck:  ## Run type checker
	uv run mypy .

check: format lint typecheck test  ## Run all checks

clean:  ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

monitor:  ## Open Grafana dashboard
	open http://localhost:3000

prometheus:  ## Open Prometheus
	open http://localhost:9090

jaeger:  ## Open Jaeger UI
	open http://localhost:16686

costs:  ## Show today's costs
	assistant costs --today --breakdown

status:  ## Check system status
	@echo "🐳 Docker Services:"
	@docker-compose ps
	@echo ""
	@echo "💰 Today's Costs:"
	@assistant costs --today || echo "  (Run 'make install' first)"

setup: install-dev docker-up  ## Complete setup (install + start services)
	@echo ""
	@echo "✅ Setup complete!"
	@echo "Run 'assistant --help' to get started"
