# SPDX-License-Identifier: GPL-2.0+

import functools
import os
import glob
import yaml
from flask import jsonify, current_app, request
from flask.config import Config
from werkzeug.exceptions import HTTPException
from greenwave.policies import Policy, Rule


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

    config.from_object(config_obj)
    config_file = os.environ.get('GREENWAVE_CONFIG', default_config_file)
    config.from_pyfile(config_file)
    if os.environ.get('SECRET_KEY'):
        config['SECRET_KEY'] = os.environ['SECRET_KEY']
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
    for policy in policies:
        if not isinstance(policy, Policy):
            raise RuntimeError('Policies are not configured properly as policy %s '
                               'is not an instance of Policy' % policy)
        for rule in policy.rules:
            if not isinstance(rule, Rule):
                raise RuntimeError('Policies are not configured properly as rule %s '
                                   'is not an instance of Rule' % rule)
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
