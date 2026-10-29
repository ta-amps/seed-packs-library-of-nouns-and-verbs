.PHONY: check packs check-tessera

# check-tessera needs a clean Tessera checkout and its Python environment, for example
#   make check-tessera TESSERA_SRC=../tessera-checkout TESSERA_ARGS=--write
TESSERA_SRC ?=
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
	@test -n "$(TESSERA_SRC)" || { echo "set TESSERA_SRC to a clean Tessera checkout that has a .venv" >&2; exit 2; }
	$(TESSERA_PYTHON) scripts/validate_against_tessera.py --tessera $(TESSERA_SRC) $(TESSERA_ARGS)
