# SPDX-License-Identifier: GPL-2.0+

import os
import glob
import yaml

from flask import Flask
from greenwave.logger import init_logging
from greenwave.api_v1 import api
from greenwave.utils import json_error

from requests import ConnectionError, Timeout
from werkzeug.exceptions import default_exceptions


def load_config(app):
    # Load default config, then override that with a config file
    if os.getenv('DEV') == 'true':
        default_config_obj = 'greenwave.config.DevelopmentConfig'
        default_config_file = os.getcwd() + '/conf/settings.py'
    elif os.getenv('TEST') == 'true':
        default_config_obj = 'greenwave.config.TestingConfig'
        default_config_file = os.getcwd() + '/conf/settings.py'
    else:
        default_config_obj = 'greenwave.config.ProductionConfig'
        default_config_file = '/etc/greenwave/settings.py'
    app.config.from_object(default_config_obj)
    config_file = os.environ.get('GREENWAVE_CONFIG', default_config_file)
    app.config.from_pyfile(config_file)
    if os.environ.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.environ['SECRET_KEY']


# applicaiton factory http://flask.pocoo.org/docs/0.12/patterns/appfactories/
def create_app(config_obj=None):
    app = Flask(__name__)
    if config_obj:
        app.config.from_object(config_obj)
    else:
        load_config(app)
    if app.config['PRODUCTION'] and app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")
    #load policies
    policy_pathnames = glob.glob(os.path.join(app.config['POLICIES_DIR'], '*.yaml'))
    app.config['policies'] = []
    for policy_pathname in policy_pathnames:
        app.config['policies'].extend(yaml.safe_load_all(open(policy_pathname, 'r')))
    # register error handlers
    for code in default_exceptions.iterkeys():
        app.register_error_handler(code, json_error)
    app.register_error_handler(ConnectionError, json_error)
    app.register_error_handler(Timeout, json_error)
    # initialize logging
    init_logging(app)
    # register blueprints
    app.register_blueprint(api, url_prefix="/api/v1.0")
    app.add_url_rule('/healthcheck', view_func=healthcheck)
    return app


def healthcheck():
    """
    Request handler for performing an application-level health check. This is
    not part of the published API, it is intended for use by OpenShift or other
    monitoring tools.

    Returns a 200 response if the application is alive and able to serve requests.
    """
    return ('Health check OK', 200, [('Content-Type', 'text/plain')])
