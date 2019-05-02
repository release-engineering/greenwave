#!/bin/bash
set -e

# Check if UID is same as owner of the mounted home directory
# (avoids creating files with wrong owner).
real_dev_id="$(stat --format %u ~)"
if [[ $real_dev_id != "$UID" ]]; then
    echo "Set correct DEV_USER_ID in .env file (should be same as owner of docker/home)."
    exit 1
fi

exec /usr/bin/gunicorn-3 \
  --reload \
  --bind=0.0.0.0:8080 \
  --access-logfile=- \
  --enable-stdio-inheritance \
  greenwave.wsgi:app
