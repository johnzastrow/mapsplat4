# QGIS plugin dev & release tasks. Plugin-specific bits live in scripts/build_plugin.sh.
# Requires: uv, zip, git, gh.   Run `make help`.
SHELL := /bin/bash
BANDIT_EXCLUDE := ./test,./tests,./docs,./.git,./lib
UNIT_TEST      := test/

.DEFAULT_GOAL := help
.PHONY: help check lint bandit secrets security test build clean tag

help:            ## list targets
	@grep -hE '^[a-z][a-z-]*:.*##' $(MAKEFILE_LIST) | sed -E 's/:[^#]*##/\t/' | sort | expand -t18

check: lint bandit secrets test  ## run EVERY publish gate (ruff+flake8, bandit, secrets, tests)

lint:            ## ruff (fast) then flake8 (authoritative pre-publish check)
	uv run --no-project --with ruff ruff check .
	uv run --no-project --with flake8 flake8 .

bandit:          ## security scan — fails on HIGH/MEDIUM (blocks plugins.qgis.org)
	uv run --no-project --with bandit bandit -r . -x $(BANDIT_EXCLUDE) -ll

secrets:         ## detect-secrets — fails if any secret is found
	@uv run --no-project --with detect-secrets detect-secrets scan \
	  | uv run --no-project python -c "import sys,json; r=json.load(sys.stdin).get('results',{}); print('secrets:', 'clean' if not r else 'FOUND '+str(list(r))); sys.exit(1 if r else 0)"

security: bandit secrets  ## bandit + secrets only

test:            ## run the headless tests (conftest mocks qgis) that CI runs
	uv run --no-project --with pytest python -m pytest $(UNIT_TEST) -q

build:           ## build the upload zip (self-verifying — no binaries/docs/cache)
	bash scripts/build_plugin.sh

clean:           ## remove caches + built artefacts
	rm -rf .ruff_cache **/__pycache__ __pycache__ *.zip resources.py

tag:             ## tag + push a release, e.g. `make tag V=0.13.2` (CI builds the zip + GitHub Release)
	@test -n "$(V)" || { echo "usage: make tag V=x.y.z"; exit 1; }
	@git diff --quiet || { echo "working tree dirty — commit first"; exit 1; }
	git tag -a v$(V) -m "v$(V)" && git push origin v$(V)
