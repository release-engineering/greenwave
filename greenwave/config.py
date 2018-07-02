# SPDX-License-Identifier: GPL-2.0+
import os


class Config(object):
    """
    A GreenWave Flask configuration.
    """
    DEBUG = True
    # We configure logging explicitly, turn off the Flask-supplied log handler.
    LOGGER_HANDLER_POLICY = 'never'
    HOST = '0.0.0.0'
    PORT = 5005
    PRODUCTION = False
    SECRET_KEY = 'replace-me-with-something-random'

    RESULTSDB_API_URL = 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0'
    WAIVERDB_API_URL = 'https://waiverdb.fedoraproject.org/api/v1.0'
    # Greenwave queries Bodhi to map builds <-> updates,
    # so that it can make decisions about updates based on results for builds.
    # If you don't have Bodhi, set this to None
    # (this effectively disables the 'bodhi_update' subject type).
    BODHI_URL = 'https://bodhi.fedoraproject.org/'

    # Options for outbound HTTP requests made by python-requests
    DIST_GIT_BASE_URL = 'https://src.fedoraproject.org/'
    DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}{pkg_namespace}/{pkg_name}/raw/{rev}/f/gating.yaml'
    KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'
    REQUESTS_TIMEOUT = (6.1, 15)
    REQUESTS_VERIFY = True

    # General options for retrying failed operations (querying external services)
    RETRY_TIMEOUT = 6
    RETRY_INTERVAL = 2

    POLICIES_DIR = '/etc/greenwave/policies'

    # By default, don't cache anything.
    CACHE = {'backend': 'dogpile.cache.null'}


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True


class DevelopmentConfig(Config):
    #RESULTSDB_API_URL = 'https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0'
    RESULTSDB_API_URL = 'http://localhost:5001/api/v2.0'
    #WAIVERDB_API_URL = 'http://waiverdb-dev.fedorainfracloud.org/api/v1.0'
    WAIVERDB_API_URL = 'http://localhost:5004/api/v1.0'
    POLICIES_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'conf',
        'policies'
    )


class TestingConfig(Config):
    RESULTSDB_API_URL = 'http://localhost:5001/api/v2.0'
    WAIVERDB_API_URL = 'http://localhost:5004/api/v1.0'
    POLICIES_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'conf',
        'policies'
    )
