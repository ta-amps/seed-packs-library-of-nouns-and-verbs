# Checks for the parametric 3D video composer pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q parametric_composer tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
