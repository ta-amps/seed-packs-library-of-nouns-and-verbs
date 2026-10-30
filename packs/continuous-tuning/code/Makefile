# Checks for the continuous tuning pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q promotion_check tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
