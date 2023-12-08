SECRET_KEY = 'greenwave'
HOST = '127.0.0.1'
PORT = 8080
DEBUG = True
POLICIES_DIR = "/etc/greenwave/policies/"
WAIVERDB_API_URL = "http://waiverdb:5004/api/v1.0"
RESULTSDB_API_URL = "http://resultsdb:5001/api/v2.0"
LISTENER_HOSTS = "umb:61612"
LISTENER_CONNECTION_SSL = None
LISTENER_CONNECTION = {
    "heartbeats": (10000, 20000),
    "keepalive": True,
    "reconnect_sleep_initial": 1.0,
    "reconnect_sleep_increase": 1.0,
    "reconnect_sleep_max": 10.0,
    "reconnect_attempts_max": 5,
}
CACHE = {
    # 'backend': 'dogpile.cache.null',
    'backend': 'dogpile.cache.pymemcache',
    'expiration_time': 1,  # 1 is 1 second, keep to see that memcached
                           # service is working
    'arguments': {
        'url': 'memcached:11211',
        'distributed_lock': True
    }
}
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'greenwave': {
            'level': 'DEBUG',
        },
        'dogpile.cache': {
            'level': 'DEBUG',
        },
        "stomp.py": {
            "level": "DEBUG",
        },
    },
    'handlers': {
        'console': {
            'formatter': 'bare',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'level': 'DEBUG',
        },
    },
    'formatters': {
        'bare': {
            'format': '[%(asctime)s] [%(process)d] [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}

OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = 'http://jaeger:4318/v1/traces'
OTEL_EXPORTER_SERVICE_NAME = "greenwave"

