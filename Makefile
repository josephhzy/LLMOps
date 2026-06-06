.PHONY: install dev test test-cov test-integration lint fmt typecheck ingest evaluate streamlit docker-build docker-up docker-down clean help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package with dev dependencies
	python -m pip install -e ".[dev]"

dev:  ## Run dev server with hot reload
	uvicorn app.api.main:create_app --factory --reload --host 0.0.0.0 --port 8000

test:  ## Run unit tests (fast, no model downloads)
	pytest -q --tb=short -m "not integration"

test-cov:  ## Run tests with coverage report
	pytest --cov=app --cov=pipelines --cov-report=term-missing --cov-report=html -m "not integration"

test-integration:  ## Run full test suite including integration tests
	pytest -q --tb=short

lint:  ## Lint with ruff
	ruff check app/ pipelines/ tests/

fmt:  ## Auto-format with ruff
	ruff format app/ pipelines/ tests/
	ruff check --fix app/ pipelines/ tests/

typecheck:  ## Run mypy type checks
	mypy app/ --ignore-missing-imports

ingest:  ## Run sample data ingestion
	python -m pipelines.ingest_pipeline

evaluate:  ## Run evaluation benchmark
	python -m pipelines.run_evaluation

streamlit:  ## Launch Streamlit frontend (port 8501)
	streamlit run streamlit_app.py --server.port 8501

docker-build:  ## Build Docker images
	docker compose build

docker-up:  ## Start services via Docker Compose
	docker compose up -d

docker-down:  ## Stop Docker services
	docker compose down

clean:  ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml *.egg-info chroma_data/
