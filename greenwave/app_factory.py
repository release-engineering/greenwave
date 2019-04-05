# SPDX-License-Identifier: GPL-2.0+

import logging
import shutil

from flask import Flask
from greenwave.api_v1 import api
from greenwave.monitor import monitor_api
from greenwave.utils import json_error, load_config, sha1_mangle_key
from greenwave.policies import load_policies, RemoteRule

from dogpile.cache import make_region
from requests import ConnectionError, Timeout
from werkzeug.exceptions import default_exceptions

log = logging.getLogger(__name__)


def _can_use_remote_rule(config):
    # Ensure that the required config settings are set for both retrieval mechanisms
    if not config.get('DIST_GIT_BASE_URL') or not config.get('KOJI_BASE_URL'):
        return False

    if config['DIST_GIT_BASE_URL'].startswith('git://'):
        # Ensure the git CLI is installed
        return bool(shutil.which('git'))
    else:
        return bool(config.get('DIST_GIT_URL_TEMPLATE'))


def _has_remote_rule(policies):
    return any(
        isinstance(rule, RemoteRule)
        for policy in policies
        for rule in policy.rules
    )


# applicaiton factory http://flask.pocoo.org/docs/0.12/patterns/appfactories/
def create_app(config_obj=None):
    app = Flask(__name__)

    app.config.update(load_config(config_obj))
    if app.config['PRODUCTION'] and app.secret_key == 'replace-me-with-something-random':
        raise Warning("You need to change the app.secret_key value for production")

    policies_dir = app.config['POLICIES_DIR']
    log.debug("config: Loading policies from %r", policies_dir)
    app.config['policies'] = load_policies(policies_dir)

    if not _can_use_remote_rule(app.config) and _has_remote_rule(app.config['policies']):
        raise RuntimeError(
            'If you want to apply a RemoteRule, you must have "DIST_GIT_BASE_URL" and '
            '"KOJI_BASE_URL" set in your configuration. Additionally, if you are using the '
            '"git archive" mechanism, the git CLI needs to be installed. If you are not, '
            'then you must set "DIST_GIT_URL_TEMPLATE" in your configuration.'
        )

    # register error handlers
    for code in default_exceptions.keys():
        app.register_error_handler(code, json_error)
    app.register_error_handler(ConnectionError, json_error)
    app.register_error_handler(Timeout, json_error)

    # register blueprints
    app.register_blueprint(api, url_prefix="/api/v1.0")
    app.register_blueprint(monitor_api, url_prefix="/api/v1.0")
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
