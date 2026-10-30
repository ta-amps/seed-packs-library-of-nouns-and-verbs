# Checks for the options chain review pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q chain_measures tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
