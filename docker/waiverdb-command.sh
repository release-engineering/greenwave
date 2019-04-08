#!/bin/bash
set -e
python3 waiverdb/manage.py wait-for-db
python3 waiverdb/manage.py db upgrade
exec /usr/bin/gunicorn-3 \
  --reload \
  --bind=0.0.0.0:5004 \
  --access-logfile=- \
  --enable-stdio-inheritance \
  waiverdb.wsgi:app
