PYTHON ?= python3

.PHONY: test check

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

check: test
