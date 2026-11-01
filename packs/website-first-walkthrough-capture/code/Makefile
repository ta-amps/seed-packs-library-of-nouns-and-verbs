PYTHON ?= python3

.PHONY: test check

test:
	$(PYTHON) -W error -m compileall -q walkthrough_capture tests
	$(PYTHON) -W error -m unittest discover -s tests -p "test_*.py" -v

check: test
