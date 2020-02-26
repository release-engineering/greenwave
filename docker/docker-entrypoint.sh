#!/bin/bash
set -e

# CA_URL is the URL of a custom root CA certificate to be installed at run-time
: ${CA_URL:=}

main() {
  # installing CA certificate
  if [ -n "${CA_URL}" ] && [ ! -f "/tmp/.ca-imported" ]; then
    # Since update-ca-trust doesn't work as a non-root user, let's just append to the bundle directly
    curl --silent --show-error --location "${CA_URL}" >> /etc/pki/tls/certs/ca-bundle.crt
    # Create a file so we know not to import it again if the container is restarted
    touch /tmp/.ca-imported
  fi
}

main

if [ -z "$GREENWAVE_CONFIG"]; then
    if [ -f /etc/greenwave/settings.py ]; then
        export GREENWAVE_CONFIG=/etc/greenwave/settings.py
    elif [ -f /src/conf/settings.py ]; then
        export GREENWAVE_CONFIG=/src/conf/settings.py
    else
        export GREENWAVE_CONFIG=/src/conf/settings.py.example
    fi
fi

if [ -z "$GREENWAVE_SUBJECT_TYPES_DIR"]; then
    if [ -d /etc/greenwave/subject_types ]; then
        export GREENWAVE_SUBJECT_TYPES_DIR=/etc/greenwave/subject_types
    else
        export GREENWAVE_SUBJECT_TYPES_DIR=/src/conf/subject_types
    fi
fi

if [ -z "$GREENWAVE_POLICIES_DIR"]; then
    if [ -d /etc/greenwave/policies ]; then
        export GREENWAVE_POLICIES_DIR=/etc/greenwave/policies
    else
        export GREENWAVE_POLICIES_DIR=/src/conf/policies
    fi
fi

exec "$@"
