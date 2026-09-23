import os

DATABASE_URI = "postgresql+psycopg2://waiverdb:waiverdb@waiverdb-db:5433/waiverdb"  # notsecret # NOSONAR

if os.getenv("TEST") == "true":
    DATABASE_URI += "_test"

HOST = "127.0.0.1"
PORT = 5004
# AUTH_METHOD = 'OIDC'
AUTH_METHOD = "dummy"
SUPERUSERS = ["dummy"]
# OIDC_CLIENT_SECRETS = '/etc/secret/client_secrets.json'
RESULTSDB_API_URL = "http://resultsdb:5001/api/v2.0"  # NOSONAR

MESSAGE_BUS_PUBLISH = os.environ.get("GREENWAVE_LISTENERS", "") not in ("", "0")
MESSAGE_PUBLISHER = "kafka"
KAFKA = {
    "topic": "eng.waiverdb.waiver.new",
    "producer": {
        "bootstrap.servers": "message-broker:9092",
        "client.id": "waiverdb",
        "retries": 3,
        "retry.backoff.ms": 100,
        "security.protocol": "PLAINTEXT",
    },
    "flush_timeout_seconds": 20.0,
}
