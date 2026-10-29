.PHONY: check packs check-tessera

# A local Tessera checkout and its Python environment, for check-tessera only.
TESSERA_SRC ?= ../tessera
TESSERA_PYTHON ?= $(TESSERA_SRC)/.venv/bin/python
TESSERA_ARGS ?=

check:
	python3 scripts/validate_examples.py
	python3 scripts/build_packs.py --check
	python3 scripts/validate_packs.py
	python3 -m unittest discover -s tests -v
	python3 scripts/check_public.py .

packs:
	python3 scripts/build_packs.py

check-tessera:
	$(TESSERA_PYTHON) scripts/validate_against_tessera.py --tessera $(TESSERA_SRC) $(TESSERA_ARGS)
