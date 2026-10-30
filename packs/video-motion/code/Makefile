# The video and motion pack's code: setup, lint, strict types, tests and demos. Run from this folder.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help setup check lint types test demo video-demo

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install the code, its video extra and test dependencies, including the pinned Tessera (uv)
	uv sync --frozen --all-groups --extra video

check: lint types test ## Lint, strict types and every test

lint: ## ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

types: ## mypy strict on video_motion/
	uv run mypy

test: ## Every test; set VIDEO_MOTION_REQUIRE_VIDEO, _TESSERA and _PACK to 1 so nothing can skip
	uv run pytest -q -rs

demo: ## Random-access frames, motion learning, multi-aspect compile and QA
	uv run video-motion demo

video-demo: ## Render and check the demo sequence in 16:9 and 9:16 (needs the video extra and Chromium)
	uv run video-motion video demo --out "$${TMPDIR:-/tmp}/video-motion-demo" --processes 2
