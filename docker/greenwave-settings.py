SECRET_KEY = 'greenwave'
HOST = '0.0.0.0'
PORT = 8080
DEBUG = True
POLICIES_DIR = '/etc/greenwave/policies/'
WAIVERDB_API_URL = 'http://waiverdb:5004/api/v1.0'
RESULTSDB_API_URL = 'http://resultsdb:5001/api/v2.0'
GREENWAVE_API_URL = 'http://dev:8080/api/v1.0'
CACHE = {
    # 'backend': "dogpile.cache.null",
    'backend': "dogpile.cache.memcached",
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
