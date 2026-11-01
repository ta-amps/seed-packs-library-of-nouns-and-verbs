# Checks for the brainstorm chunking and situation miner pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q brainstorm_miner tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
