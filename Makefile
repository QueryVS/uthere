SHELL := /bin/bash

PYTHON ?= python3
DB ?= $(HOME)/.local/state/uthere/uthere.db
SOCKET ?= /tmp/uthere.sock

.PHONY: help install run clean reset test package

help:
	@echo "Targets:"
	@echo "  make install  Install uthere as a systemd service via scripts/install-systemd.sh"
	@echo "  make run      Run the service in the foreground"
	@echo "  make clean    Remove local build, test, and Python cache files"
	@echo "  make reset    Clean and remove the local development DB/socket"
	@echo "  make test     Run the test suite"
	@echo "  make package  Generate Debian/Fedora/Gentoo packaging files"
	@echo ""
	@echo "Variables:"
	@echo "  DB=$(DB)"
	@echo "  SOCKET=$(SOCKET)"

install:
	sudo scripts/install-systemd.sh

run:
	PYTHONPATH=src UTHERE_DB="$(DB)" UTHERE_SOCKET="$(SOCKET)" $(PYTHON) -m uthere serve

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info src/*.egg-info

reset: clean
	rm -f "$(DB)" "$(SOCKET)"
	@echo "Reset local development state."

test:
	PYTHONPATH=src pytest -q

package:
	PYTHONPATH=src $(PYTHON) -m uthere.packager all
