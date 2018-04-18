# SPDX-License-Identifier: GPL-2.0+

from flask import Flask
from greenwave.logger import init_logging
from greenwave.api_v1 import api
from greenwave.utils import json_error, load_config

from dogpile.cache import make_region
from dogpile.cache.util import sha1_mangle_key
from requests import ConnectionError, Timeout
from werkzeug.exceptions import default_exceptions


# applicaiton factory http://flask.pocoo.org/docs/0.12/patterns/appfactories/
def create_app(config_obj=None):
    app = Flask(__name__)

    app.config.update(load_config(config_obj))
    if app.config['PRODUCTION'] and app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")

    # register error handlers
    for code in default_exceptions.keys():
        app.register_error_handler(code, json_error)
    app.register_error_handler(ConnectionError, json_error)
    app.register_error_handler(Timeout, json_error)

    # initialize logging
    init_logging(app)

    # register blueprints
    app.register_blueprint(api, url_prefix="/api/v1.0")
    app.add_url_rule('/healthcheck', view_func=healthcheck)

    # Initialize the cache.
    app.cache = make_region(key_mangler=sha1_mangle_key)
    app.cache.configure(**app.config['CACHE'])

    return app


def healthcheck():
    """
    Request handler for performing an application-level health check. This is
    not part of the published API, it is intended for use by OpenShift or other
    monitoring tools.

    Returns a 200 response if the application is alive and able to serve requests.
    """
    return ('Health check OK', 200, [('Content-Type', 'text/plain')])
