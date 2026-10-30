# Checks for the codebase health review pack's code: standard library only, warnings are errors.
# CI sets HEALTH_CHECKS_REQUIRE_GIT=1 so a missing git fails instead of skipping the blame tests.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q health_checks tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
