PYTHON ?= python3
NODE ?= node

.PHONY: test js check

test:
	$(PYTHON) -W error -m compileall -q request_status_ui tests
	$(PYTHON) -W error -m unittest discover -s tests -p "test_*.py" -v

js:
	$(NODE) tests/js_parity.mjs

check: test js
