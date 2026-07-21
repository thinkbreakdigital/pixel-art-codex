SHELL := /bin/bash
PYTHON := .venv/bin/python
PIXEL_ART := $(PYTHON) -m pixel_art_pipeline.cli

.PHONY: install validate test check info open clean

install:
	./scripts/build.sh

validate:
	$(PIXEL_ART) validate-spec
	$(PIXEL_ART) validate-assets

test:
	$(PYTHON) -m pytest

check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy src
	$(PYTHON) -m pytest
	@for script in scripts/*.sh; do bash -n "$$script"; done

info:
	$(PIXEL_ART) info

open:
	@test -n "$(FILE)" || { echo "error: FILE is required (make open FILE=/path/to/asset)" >&2; exit 2; }
	./scripts/open_in_pixelorama.sh "$(FILE)"

clean:
	./scripts/clean.sh

