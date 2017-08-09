# SPDX-License-Identifier: GPL-2.0+

import os
import glob
import yaml
from flask import jsonify, current_app
from flask.config import Config
from werkzeug.exceptions import HTTPException


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
    return response


def load_config(config_obj=None):
    """
    Load Greenwave configuration. If the config_obj is given, it will load the
    configuration from there. Otherwise, it will load the configuration based on
    how the environment is configured.
    :param str config_obj: An config object. For example, greenwave.config.DevelopmentConfig.
    :return: A dict of Greenwave configuration.
    """
    config = Config(__name__)
    if config_obj:
        config.from_object(config_obj)
    else:
        # Load default config, then override that with a config file
        default_config_file = None
        if os.getenv('DEV') == 'true':
            default_config_obj = 'greenwave.config.DevelopmentConfig'
        elif os.getenv('TEST') == 'true':
            default_config_obj = 'greenwave.config.TestingConfig'
        else:
            default_config_obj = 'greenwave.config.ProductionConfig'
            default_config_file = '/etc/greenwave/settings.py'
        config.from_object(default_config_obj)
        config_file = os.environ.get('GREENWAVE_CONFIG', default_config_file)
        if config_file:
            config.from_pyfile(config_file)
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
    return policies
