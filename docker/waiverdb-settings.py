import os

DATABASE_URI = 'postgresql+psycopg2://waiverdb:waiverdb@waiverdb-db:5433/waiverdb'

if os.getenv('TEST') == 'true':
    DATABASE_URI += '_test'

HOST = '0.0.0.0'
PORT = 5004
#AUTH_METHOD = 'OIDC'
AUTH_METHOD = 'dummy'
MESSAGE_BUS_PUBLISH = False
SUPERUSERS = ['dummy']
#OIDC_CLIENT_SECRETS = '/etc/secret/client_secrets.json'
RESULTSDB_API_URL = 'http://resultsdb:5001/api/v2.0'
