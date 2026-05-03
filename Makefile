SHELL := /bin/bash

PYTHON ?= python3
DB ?= /var/lib/uthere/uthere.db
SOCKET ?= /tmp/uthere.sock

.PHONY: help install install-root install-user run clean reset test package docker-build

help:
	@echo "Targets:"
	@echo "  make install       Show install mode choices"
	@echo "  make install-root  Install uthere as a root/systemd service"
	@echo "  make install-user  Install uthere into the current user's home directory"
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
	@echo "Choose an install mode:"
	@echo "  make install-root  # root/systemd service, continuous background checks"
	@echo "  make install-user  # user-home CLI install, runs only when called"

install-root:
	@if [[ "$${EUID}" -eq 0 ]]; then \
		scripts/install-systemd.sh; \
	else \
		su -c 'cd "$(CURDIR)" && scripts/install-systemd.sh'; \
	fi

install-user:
	scripts/install-systemd.sh

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

docker-build:
	docker build -t uthere:latest .

docker-run:
	docker run --rm -d -v uthere-data:/var/lib/uthere uthere:latest

docker-cli:
	docker run -it uthere bash
