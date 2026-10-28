.PHONY: check
check:
	python3 scripts/validate_examples.py
	python3 -m unittest discover -s tests -v
	python3 scripts/check_public.py .
