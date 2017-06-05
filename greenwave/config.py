
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.


class Config(object):
    """
    A GreenWave Flask configuration.
    """
    DEBUG = True
    JOURNAL_LOGGING = False
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
