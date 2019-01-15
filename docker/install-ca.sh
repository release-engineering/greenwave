#!/bin/bash
set -e

if [ -n "${CA_URL}" ] && [ ! -f "/tmp/.imported" ]; then
    # Since update-ca-trust doesn't work as a non-root user, let's just append to the bundle directly
    curl --silent --show-error "${CA_URL}" >> /etc/pki/tls/certs/ca-bundle.crt
    # Create a file so we know not to import it again if the container is restarted
    touch /tmp/.imported
fi
