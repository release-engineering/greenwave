# SPDX-License-Identifier: GPL-2.0+

import os

from flask import Flask
from greenwave.logger import init_logging
from greenwave.api_v1 import api
from requests import ConnectionError, Timeout


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


# applicaiton factory http://flask.pocoo.org/docs/0.12/patterns/appfactories/
def create_app(config_obj=None):
    app = Flask(__name__)
    if config_obj:
        app.config.from_object(config_obj)
    else:
        load_config(app)
    if app.config['PRODUCTION'] and app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")
    # register error handlers
    app.register_error_handler(ConnectionError, lambda e: (str(e), 503))
    app.register_error_handler(Timeout, lambda e: (str(e), 503))
    # initialize logging
    init_logging(app)
    # register blueprints
    app.register_blueprint(api, url_prefix="/api/v1.0")
    return app
