#!/bin/bash
set -xeuo pipefail

image=$1

uv version "2.3.0.dev$COMMIT_TIMESTAMP+git.$SHORT_COMMIT" &&

sed -i "s/ build: .*/ image: $image/" docker-compose.yml
echo "Using images:" && grep -E " image:| build: " docker-compose.yml

trap "uvx --with podman-compose podman-compose down" QUIT TERM INT HUP EXIT
uvx --with podman-compose podman-compose --verbose pull
uvx --with podman-compose podman-compose --verbose up --no-build -d

uvx --with tox-uv tox -e functional -- --no-cov functional-tests
