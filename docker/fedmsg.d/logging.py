config = dict(logging={
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "bare": {
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "format": "[%(asctime)s][%(name)10s %(levelname)7s] %(message)s"
        }
    },
    "loggers": {
        "greenwave": {
            "handlers": ["console"], "propagate": True, "level": "DEBUG"
        },
        "moksha": {
            "handlers": ["console"], "propagate": False, "level": "DEBUG"
        },
        "requests": {
            "handlers": ["console"], "propagate": False, "level": "DEBUG"
        },
        "resultsdb_handler": {
            "handlers": ["console"], "propagate": False, "level": "DEBUG"
        },
        "waiverdb_handler": {
            "handlers": ["console"], "propagate": False, "level": "DEBUG"
        },
        "dogpile": {
            "handlers": ["console"], "propagate": False, "level": "DEBUG"
        },
    },
    "handlers": {
        "console": {
            "formatter": "bare",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "DEBUG"
        }
    },
})
