# Checks for the scene and cognitive video QA pack's code: standard library only, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile

check: compile test

compile:
	$(PYTHON) -W error -m compileall -q scene_cognitive_qa tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
