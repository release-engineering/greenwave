#!/bin/bash
COMPOSE=${COMPOSE:-podman-compose}

healthcheck() {
    name=$1
    url=$2
    if ! curl --retry-all-errors --retry 5 --silent --fail-with-body "$url"; then
        echo "ERROR: Health check for $name FAILED"
        echo "--- Logs for $name ---"
        "$COMPOSE" logs "$name"
        exit 1
    fi
    echo
}

echo "Health check waiverdb"
healthcheck waiverdb http://localhost:5004/healthcheck

echo "Health check resultsdb"
healthcheck resultsdb http://localhost:5001/api/v2.0/healthcheck

echo "Health check greenwave"
healthcheck greenwave http://localhost:8080/healthcheck
