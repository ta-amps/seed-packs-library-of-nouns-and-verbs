# Checks for the handwritten statements kit's sample renderer: lint, format check and tests.
.DEFAULT_GOAL := help
SHELL := /bin/bash
OUT ?=

.PHONY: help setup check lint test render

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install the locked environment (uv)
	uv sync --locked --all-groups

check: lint test ## Lint, format check and tests

lint: ## ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

test: ## Rebuild every sample page and compare it with the test-cases noun
	uv run pytest -q

render: ## Write the sample pages to OUT, a folder outside the library
	@test -n "$(OUT)" || { echo "set OUT to a folder outside the library" >&2; exit 2; }
	uv run python render_samples.py --out "$(OUT)" --check
