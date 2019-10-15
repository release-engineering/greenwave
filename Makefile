COMPOSE := docker-compose
BROWSER := xdg-open

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
	@echo '  make flake8 - executes flake8 in dev container'
	@echo
	@echo '  make pylint - executes pylint in dev container'
	@echo
	@echo '  make test - alias for "make pytest flake8 pylint"'
	@echo
	@echo '  make coverage [ARGS=".."] - generates and shows test code coverage'

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

recreate:
	$(COMPOSE) up -d --force-recreate

# Executes CMD in dev container.
# Usage: make exec CMD="python3 -m pytest -x"
exec: up
	$(COMPOSE) exec dev bash -c '$(CMD)'

sudo: up
	$(COMPOSE) exec -u root dev bash -c '$(CMD)'

test: pytest flake8 pylint

pytest:
	$(MAKE) exec \
	    CMD="pip3 install --user -r dev-requirements.txt && COVERAGE_FILE=/home/dev/.coverage python3 -m pytest $(ARGS)"

flake8:
	python -m flake8

pylint:
	python -m pylint greenwave/

coverage:
	$(MAKE) pytest ARGS="--cov-config .coveragerc --cov=greenwave --cov-report html:/home/dev/htmlcov $(ARGS)"
	$(BROWSER) docker/home/htmlcov/index.html
