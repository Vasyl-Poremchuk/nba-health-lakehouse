# Treat the following commands as real commands, even if files with same names exist
.PHONY: help setup lint format clean test adr typecheck check up down

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Install dependencies and wire git hooks
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

lint:  ## Lint with ruff
	uv run ruff check .

format:  ## Auto-format with ruff
	uv run ruff format .

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build
	find . -type d -name __pycache__ -exec rm -rf {} +

test:  ## Run the test suite
	uv run pytest -v

adr:  ## Create a new ADR from the template (usage: make adr N=0012 TITLE=my-decision)
	cp docs/adr/0000-template.md docs/adr/${N}-${TITLE}.md
	@echo "Created docs/adr/${N}-${TITLE}.md"

typecheck:  ## Type-check with mypy
	uv run mypy src pipelines

check:  lint typecheck test  ## Run all checks (lint + types + tests)

up:  ## Create and start containers
	docker compose up airflow-init && docker compose up

down:  ## Stop and remove containers, networks, named volumes, and images
	docker compose down --volumes --rmi all
