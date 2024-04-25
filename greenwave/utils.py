# SPDX-License-Identifier: GPL-2.0+

import datetime
import functools
import hashlib
import logging
import os

import requests
from flask import current_app, jsonify, request
from flask.config import Config
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


def json_error(error):
    """
    Return error responses in JSON.

    :param error: One of Exceptions. It could be HTTPException, ConnectionError, or
    Timeout.
    :return: JSON error response.

    """
    if isinstance(error, HTTPException):
        msg = error.description
        status_code = error.code
        current_app.logger.info("HTTP request failed: %s", error)
    elif isinstance(error, (ConnectionError, requests.ConnectionError)):
        current_app.logger.exception("Connection error: %s", error)
        msg = f"Error connecting to upstream server: {error}"
        status_code = 502
    elif isinstance(error, requests.Timeout):
        current_app.logger.exception("Timeout error: %s", error)
        msg = f"Timeout connecting to upstream server: {error}"
        status_code = 504
    else:
        current_app.logger.exception("Unexpected server error: %s", error)
        msg = "Server encountered unexpected error"
        status_code = 500

    response = jsonify(message=msg)
    response.status_code = status_code

    response = insert_headers(response)

    return response


def jsonp(func):
    """Wraps Jsonified output for JSONP requests."""

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        callback = request.args.get("callback", False)
        if callback:
            resp = func(*args, **kwargs)
            resp.set_data(
                "{}({});".format(str(callback), resp.get_data().decode("utf-8"))
            )
            resp.mimetype = "application/javascript"
            return resp
        else:
            return func(*args, **kwargs)

    return wrapped


def load_config(config_obj=None):
    """
    Load Greenwave configuration. It will load the configuration based on how the environment is
    configured.
    :return: A dict of Greenwave configuration.
    """
    # Load default config, then override that with a config file
    config = Config(__name__)
    if config_obj is None:
        if os.getenv("TEST") == "true":
            config_obj = "greenwave.config.TestingConfig"
        elif os.getenv("DEV") == "true" or os.getenv("DOCS") == "true":
            config_obj = "greenwave.config.DevelopmentConfig"
        else:
            config_obj = "greenwave.config.ProductionConfig"

    if os.getenv("TEST") == "true":
        default_config_file = os.path.join(os.getcwd(), "conf", "settings.py.example")
    elif os.getenv("DEV") == "true":
        default_config_file = os.path.join(os.getcwd(), "conf", "settings.py")
    elif os.getenv("DOCS") == "true":
        default_config_file = os.path.normpath(
            os.path.join(os.getcwd(), "..", "conf", "settings.py.example")
        )
    else:
        default_config_file = "/etc/greenwave/settings.py"

    # 1. Load default configuration.
    log.debug("config: Loading config from %r", config_obj)
    config.from_object(config_obj)

    # 2. Override default configuration with environment variables.
    if os.environ.get("GREENWAVE_SUBJECT_TYPES_DIR"):
        config["SUBJECT_TYPES_DIR"] = os.environ["GREENWAVE_SUBJECT_TYPES_DIR"]

    if os.environ.get("GREENWAVE_POLICIES_DIR"):
        config["POLICIES_DIR"] = os.environ["GREENWAVE_POLICIES_DIR"]

    # 3. Override default configuration and environment variables with custom config file.
    config_file = os.environ.get("GREENWAVE_CONFIG", default_config_file)
    log.debug("config: Extending config with %r", config_file)
    config.from_pyfile(config_file)

    if os.environ.get("SECRET_KEY"):
        config["SECRET_KEY"] = os.environ["SECRET_KEY"]

    return config


def insert_headers(response):
    """Insert the CORS headers for the give reponse if there are any
    configured for the application.
    """
    if current_app.config.get("CORS_URL"):
        response.headers["Access-Control-Allow-Origin"] = current_app.config["CORS_URL"]
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Method"] = "POST, OPTIONS"
    return response


def mangle_key(key):
    """
    Like dogpile.cache.util.sha1_mangle_key, but works correctly on
    Python 3 with str keys (which must be encoded to bytes before passing them
    to hashlib.sha1()).
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def add_to_timestamp(timestamp, **kwargs):
    """
    A utility function that takes a timestamp with format %Y-%m-%dT%H:%M:%S.%f
    and returns the microsecond before that timestamp. It returns always a
    %Y-%m-%dT%H:%M:%S.%f format. It is useful to detect at which moment we should
    ask for a decision before a specific timestamp (example: the creation of a
    result).
    """
    delta = datetime.timedelta(**kwargs)

    date_format = "%Y-%m-%dT%H:%M:%S.%f"

    if timestamp.endswith(" UTC"):
        # date/time format submitted by resultsdb using fedora-messaging
        from_date_format = "%Y-%m-%d %H:%M:%S UTC"
    else:
        from_date_format = date_format

    return datetime.datetime.strftime(
        datetime.datetime.strptime(timestamp, from_date_format) + delta, date_format
    )


def right_before_this_time(timestamp):
    return add_to_timestamp(timestamp, microseconds=-1)
