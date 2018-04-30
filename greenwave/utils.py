# SPDX-License-Identifier: GPL-2.0+

import functools
import glob
import logging
import os
import time

import yaml
from flask import jsonify, current_app, request
from flask.config import Config
from werkzeug.exceptions import HTTPException
import greenwave.policies

log = logging.getLogger(__name__)


def json_error(error):
    """
    Return error responses in JSON.

    :param error: One of Exceptions. It could be HTTPException, ConnectionError, or
    Timeout.
    :return: JSON error response.

    """
    if isinstance(error, HTTPException):
        response = jsonify(message=error.description)
        response.status_code = error.code
    else:
        # Could be ConnectionError or Timeout
        current_app.logger.exception('Returning 500 to user.')
        response = jsonify(message=str(error.message))
        response.status_code = 500

    response = insert_headers(response)

    return response


def jsonp(func):
    """Wraps Jsonified output for JSONP requests."""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            resp = func(*args, **kwargs)
            resp.set_data('{}({});'.format(
                str(callback),
                resp.get_data()
            ))
            resp.mimetype = 'application/javascript'
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
        if os.getenv('DEV') == 'true':
            config_obj = 'greenwave.config.DevelopmentConfig'
        elif os.getenv('TEST') == 'true':
            config_obj = 'greenwave.config.TestingConfig'
        else:
            config_obj = 'greenwave.config.ProductionConfig'

    if os.getenv('DEV') == 'true' or os.getenv('TEST') == 'true':
        default_config_file = os.getcwd() + '/conf/settings.py'
    else:
        default_config_file = '/etc/greenwave/settings.py'

    log.debug("config: Loading config from %r", config_obj)
    config.from_object(config_obj)

    config_file = os.environ.get('GREENWAVE_CONFIG', default_config_file)
    log.debug("config: Extending config with %r", config_file)
    config.from_pyfile(config_file)

    if os.environ.get('SECRET_KEY'):
        config['SECRET_KEY'] = os.environ['SECRET_KEY']

    log.debug("config: Loading policies from %r", config['POLICIES_DIR'])
    config['policies'] = load_policies(config['POLICIES_DIR'])

    return config


def load_policies(policies_dir):
    """
    Load Greenwave policies from the given policies directory.

    :param str policies_dir: A path points to the policies directory.
    :return: A list of policies.

    """
    policy_pathnames = glob.glob(os.path.join(policies_dir, '*.yaml'))
    policies = []
    for policy_pathname in policy_pathnames:
        policies.extend(yaml.safe_load_all(open(policy_pathname, 'r')))
    greenwave.policies.validate_policies(policies)
    return policies


def insert_headers(response):
    """ Insert the CORS headers for the give reponse if there are any
    configured for the application.
    """
    if current_app.config.get('CORS_URL'):
        response.headers['Access-Control-Allow-Origin'] = \
            current_app.config['CORS_URL']
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Method'] = 'POST, OPTIONS'
    return response


def retry(timeout=None, interval=None, wait_on=Exception):
    """ A decorator that allows to retry a section of code...
    ...until success or timeout.

    If omitted, the values for `timeout` and `interval` are
    taken from the global configuration.
    """
    def wrapper(function):
        @functools.wraps(function)
        def inner(*args, **kwargs):
            _timeout = timeout or current_app.config['RETRY_TIMEOUT']
            _interval = interval or current_app.config['RETRY_INTERVAL']
            # These can be configured per-function, or globally if omitted.
            start = time.time()
            while True:
                try:
                    return function(*args, **kwargs)
                except wait_on as e:  # pylint: disable=broad-except
                    log.warning("Exception %r raised from %r.  Retry in %rs",
                                e, function, _interval)
                    time.sleep(_interval)
                    if (time.time() - start) >= _timeout:
                        raise  # This re-raises the last exception.
        return inner
    return wrapper
