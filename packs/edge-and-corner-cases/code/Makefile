# Checks for the edge and corner cases pack's code: standard library only, warnings are errors.
# CI sets EDGE_CASES_REQUIRE_TZDATA=1 so a missing time zone database fails instead of skipping.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q edge_cases tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
