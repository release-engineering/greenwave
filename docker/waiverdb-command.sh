#!/bin/bash
set -e
waiverdb wait-for-db
waiverdb db upgrade
exec /usr/bin/gunicorn-3 \
  --reload \
  --bind=0.0.0.0:5004 \
  --access-logfile=- \
  --enable-stdio-inheritance \
  waiverdb.wsgi:app
