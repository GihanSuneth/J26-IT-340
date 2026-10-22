# Lightweight, repository-local verification commands.

PYTHON ?= component3/.venv/bin/python

.PHONY: test test-component3 frontend-build evidence check

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -p no:cacheprovider backend component3/backend tests/contract -q

test-component3:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -p no:cacheprovider component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests -q

frontend-build:
	npm --prefix frontend/trolley-display run build

evidence:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -B component3/docs/research_evidence/tools/validate_evidence.py

check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m compileall -q backend component3/backend shared
	git diff --check
