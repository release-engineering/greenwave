# Use podman-compose by default if available.
ifeq (, $(shell which podman-compose))
    COMPOSE := docker-compose
    PODMAN := docker
else
    COMPOSE := podman-compose
    PODMAN := podman
endif

BROWSER := xdg-open
SERVICE := dev

PYTHON_VERSION_VENV := python3.9

POETRY_RUN := poetry run
PYTEST := pytest --color=yes
PIP_INSTALL := pip3 install --no-cache-dir --user

all: help

help:
	@echo 'Usage:'
	@echo
	@echo '  make up - starts containers in docker-compose environment'
	@echo
	@echo '  make down - stops containers in docker-compose environment'
	@echo
	@echo '  make build - builds container images for docker-compose environment'
	@echo
	@echo '  make recreate - recreates containers for docker-compose environment'
	@echo
	@echo '  make exec [CMD=".."] - executes command in dev container'
	@echo
	@echo '  make sudo [CMD=".."] - executes command in dev container under root user'
	@echo
	@echo '  make pytest [ARGS=".."] - executes pytest with given arguments in dev container'
	@echo
	@echo '  make test - alias for "make pytest"'
	@echo
	@echo '  make coverage [ARGS=".."] - generates and shows test code coverage'
	@echo
	@echo 'Variables:'
	@echo
	@echo '  COMPOSE=docker-compose|podman-compose'
	@echo '    - docker-compose or podman-compose command'
	@echo '      (default is "podman-compose" if available)'
	@echo
	@echo '  PODMAN=docker|podman'
	@echo '    - docker or podman command'
	@echo '      (default is "podman" if "podman-compose" is available)'
	@echo
	@echo '  SERVICE={dev|waiverdb|resultsdb|waiverdb-db|resultsdb-db|memcached}'
	@echo '    - service for which to run `make exec` and similar (default is "dev")'
	@echo '      Example: make exec SERVICE=waiverdb CMD=flake8'

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

recreate:
	$(COMPOSE) up -d --force-recreate

exec:
	$(PODMAN) exec greenwave_$(SERVICE)_1 bash -c '$(CMD)'

sudo:
	$(PODMAN) exec -u root greenwave_$(SERVICE)_1 bash -c '$(CMD)'

test:
	$(MAKE) exec CMD="$(PIP_INSTALL) poetry"
	$(MAKE) exec CMD="poetry install --no-root"
	$(MAKE) pytest

pytest:
	$(MAKE) exec \
	    CMD="COVERAGE_FILE=/home/dev/.coverage-$(SERVICE) $(POETRY_RUN) $(PYTEST) $(ARGS)"

coverage:
	$(MAKE) pytest ARGS="--cov-config .coveragerc --cov=greenwave --cov-report html:/home/dev/htmlcov-$(SERVICE) $(ARGS)"
	$(BROWSER) docker/home/htmlcov-$(SERVICE)/index.html
