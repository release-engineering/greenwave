# SPDX-License-Identifier: GPL-2.0+


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


class ProductionConfig(Config):
    DEBUG = False
    PRODUCTION = True


class DevelopmentConfig(Config):
    RESULTSDB_API_URL = 'https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0'
    WAIVERDB_API_URL = 'http://waiverdb-dev.fedorainfracloud.org/api/v1.0'


class TestingConfig(Config):
    RESULTSDB_API_URL = 'https://resultsdb.domain.local/api/v2.0'
    WAIVERDB_API_URL = 'https://waiverdb.domain.local/api/v1.0'
