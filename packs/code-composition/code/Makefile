# Checks for the code-composition pack's tested code: lint, types, tests, demo and the pinned Tessera integration.
.DEFAULT_GOAL := help
SHELL := /bin/bash
TESSERA_DIR ?=

.PHONY: help setup check lint types test demo tessera-integration

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

setup: ## Install the locked Python dependencies (uv)
	uv sync --locked --all-groups

check: lint types test ## Lint, format check, strict types and tests

lint: ## ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

types: ## mypy strict on code_composition/
	uv run mypy

test: ## Unit and integration tests
	uv run pytest -q

demo: ## Verify all 18 prewritten nodes, compile & execute 3 DAG recipes, prove Python equivalence & warm cache hits
	CODE_COMPOSITION_DB=$$(mktemp -d)/code-composition.db uv run code-composition demo

tessera-integration: ## Seed export against real Tessera models and HTTP (TESSERA_DIR: prepared checkout)
	@test -n "$(TESSERA_DIR)" || { echo "set TESSERA_DIR to a Tessera checkout prepared with uv sync --locked --all-extras" >&2; exit 2; }
	CODE_COMPOSITION_REQUIRE_TESSERA=1 PYTHONPATH="$(CURDIR)" "$(TESSERA_DIR)/.venv/bin/python" -m pytest -q -p no:cacheprovider tests/test_seed_pack_tessera.py
