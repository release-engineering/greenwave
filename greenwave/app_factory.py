# SPDX-License-Identifier: GPL-2.0+

import logging
import logging.config

from flask import Flask
from greenwave.api_v1 import api, landing_page
from greenwave.utils import json_error, load_config, mangle_key
from greenwave.policies import load_policies
from greenwave.subjects.subject_type import load_subject_types
from greenwave.tracing import init_tracing

from dogpile.cache import make_region
import requests
from werkzeug.exceptions import default_exceptions

log = logging.getLogger(__name__)


# applicaiton factory http://flask.pocoo.org/docs/0.12/patterns/appfactories/
def create_app(config_obj=None):
    app = Flask(__name__)

    app.config.update(load_config(config_obj))
    if app.config['PRODUCTION'] and app.secret_key == 'replace-me-with-something-random':  # nosec
        raise Warning("You need to change the app.secret_key value for production")

    logging_config = app.config.get('LOGGING')
    if logging_config:
        logging.config.dictConfig(logging_config)

    init_tracing(app)

    policies_dir = app.config['POLICIES_DIR']
    log.debug("config: Loading policies from %r", policies_dir)
    app.config['policies'] = load_policies(policies_dir)

    subject_types_dir = app.config['SUBJECT_TYPES_DIR']
    log.debug("config: Loading subject types from %r", subject_types_dir)
    app.config['subject_types'] = load_subject_types(subject_types_dir)

    if app.config.get('DIST_GIT_URL_TEMPLATE') and app.config.get('DIST_GIT_BASE_URL'):
        app.config['DIST_GIT_URL_TEMPLATE'] = app.config['DIST_GIT_URL_TEMPLATE'].replace(
            '{DIST_GIT_BASE_URL}', app.config['DIST_GIT_BASE_URL']
        )

    # register error handlers
    for code in default_exceptions.keys():
        app.register_error_handler(code, json_error)
    app.register_error_handler(ConnectionError, json_error)
    app.register_error_handler(requests.ConnectionError, json_error)
    app.register_error_handler(requests.Timeout, json_error)

    # register blueprints
    app.register_blueprint(api, url_prefix="/api/v1.0")
    app.add_url_rule('/', view_func=landing_page)
    app.add_url_rule('/healthcheck', view_func=healthcheck)

    # Initialize the cache.
    app.cache = make_region(key_mangler=mangle_key)
    app.cache.configure(**app.config['CACHE'])

    return app


def healthcheck():
    """
    Request handler for performing an application-level health check. This is
    not part of the published API, it is intended for use by OpenShift or other
    monitoring tools.

    Returns a 200 response if the application is alive and able to serve requests.
    """
    return 'Health check OK', 200, [('Content-Type', 'text/plain')]
