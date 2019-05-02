#!/bin/bash
set -e
resultsdb init_db
exec mod_wsgi-express-3 start-server /usr/share/resultsdb/resultsdb.wsgi \
    --user apache --group apache \
    --port 5001 --threads 5 \
    --include-file /etc/httpd/conf.d/resultsdb.conf \
    --log-level info \
    --log-to-terminal \
    --access-log \
    --startup-log
