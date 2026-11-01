# Checks for the Meta ARE scenario matrix pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q scenario_matrix tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
