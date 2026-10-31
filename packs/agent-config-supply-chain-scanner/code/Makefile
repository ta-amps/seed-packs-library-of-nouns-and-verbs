# Checks for the agent config supply chain scanner pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q config_scanner tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
