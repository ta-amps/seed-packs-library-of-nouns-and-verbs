# Checks for the frame-by-frame video QA pack's code: pinned packages, warnings are errors.
PYTHON ?= python3

.PHONY: check test compile install

check: compile test

install:
	$(PYTHON) -m pip install --no-deps -r requirements.txt

compile:
	$(PYTHON) -W error -m compileall -q frame_qa tests

test:
	$(PYTHON) -W error -m unittest discover -s tests -v
