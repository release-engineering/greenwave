#!/bin/bash
set -e
waiverdb wait-for-db
waiverdb db upgrade
exec gunicorn \
  --reload \
  --bind=0.0.0.0:5004 \
  --access-logfile=- \
  --enable-stdio-inheritance \
  waiverdb.wsgi:app
