import os

SECRET_KEY = "resultsdb"  # nosec
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://resultsdb:resultsdb@resultsdb-db:5432/resultsdb"  # notsecret # NOSONAR
FILE_LOGGING = False
LOGFILE = "/var/log/resultsdb/resultsdb.log"
SYSLOG_LOGGING = False
STREAM_LOGGING = True
RUN_HOST = "127.0.0.1"
RUN_PORT = 5001
ADDITIONAL_RESULT_OUTCOMES = ("RUNNING", "QUEUED", "ERROR")

MESSAGE_BUS_PUBLISH = os.environ.get("GREENWAVE_LISTENERS", "") not in ("", "0")
MESSAGE_BUS_PLUGIN = "stomp"
MESSAGE_BUS_KWARGS = {
    "modname": "resultsdb",
    "destination": "/topic/VirtualTopic.eng.resultsdb.result.new",
    "connection": {
        "host_and_ports": [("umb", 61612)],
        "use_ssl": False,
    },
}
