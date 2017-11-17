# SPDX-License-Identifier: GPL-2.0+
import os


class Config(object):
    """
    A GreenWave Flask configuration.
    """
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 5005
    PRODUCTION = False
    SECRET_KEY = 'replace-me-with-something-random'
    RESULTSDB_API_URL = 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0'
    WAIVERDB_API_URL = 'https://waiverdb.fedoraproject.org/api/v1.0'
    REQUESTS_TIMEOUT = (6.1, 15)
    POLICIES_DIR = '/etc/greenwave/policies'
    # By default, don't cache anything.
    CACHE = {'backend': 'dogpile.cache.null'}

    # These are keys used to construct announcements about decision changes.
    ANNOUNCEMENT_SUBJECT_KEYS = [
        ('item', 'type',),
        ('original_spec_nvr',),
        ('productmd.compose.id',),
    ]


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


class CachedTestingConfig(TestingConfig):
    PORT = 6005
    # Cache in memory
    CACHE = dict(
        backend="dogpile.cache.dbm",
        expiration_time=300,
        arguments={"filename": "greenwave-test-cache.dbm"}
    )
