# SPDX-License-Identifier: GPL-2.0+

import os
import sys
import time
import textwrap
import itertools
import json
import logging
import subprocess
import socket
import pytest
import requests

from contextlib import contextmanager
from mock import patch
from sqlalchemy import create_engine

from greenwave.logger import init_logging


log = logging.getLogger(__name__)


# It's all local, and so should be fast enough.
TEST_HTTP_TIMEOUT = int(os.environ.get('TEST_HTTP_TIMEOUT', 2))


@pytest.fixture(scope='session', autouse=True)
def logging():
    init_logging()
    # We don't configure any log handlers, let pytest capture the log
    # messages and display them instead.


def drop_and_create_database(dbname):
    """
    Drops (if exists) and re-creates the given database on the local Postgres instance.
    """
    engine = create_engine('postgresql+psycopg2:///template1')
    with engine.connect() as connection:
        connection.execution_options(isolation_level='AUTOCOMMIT')
        connection.execute('DROP DATABASE IF EXISTS {}'.format(dbname))
        connection.execute('CREATE DATABASE {}'.format(dbname))
    engine.dispose()


def wait_for_listen(port):
    """
    Waits until something is listening on the given TCP port.
    """
    for attempt in range(50):
        try:
            s = socket.create_connection(('127.0.0.1', port), timeout=1)
            s.close()
            return
        except socket.error:
            time.sleep(0.1)
    raise RuntimeError('Gave up waiting for port %s' % port)


@contextmanager
def server_subprocess(
        name, port, start_server_arguments,
        api_base='/api/v1.0',
        source_path=None,
        settings_content=None, tmpdir_factory=None,
        dbname=None, init_db_arguments=None):
    """
    Starts a server as subprocess and returns address.
    """
    env_var_prefix = name.upper()

    # <NAME>_TEST_URL environment variable overrides address and avoids
    # creating test process.
    test_url_env_var = env_var_prefix + '_TEST_URL'
    if test_url_env_var in os.environ:
        url = os.environ[test_url_env_var]
        config = f'greenwave.config.TestingConfig.{env_var_prefix}_API_URL'
        with patch(config, url + api_base):
            yield url
            return

    if source_path is None:
        default_source_path = os.path.join('..', name)
        source_path = os.environ.get(env_var_prefix, default_source_path)
        if not os.path.isdir(source_path):
            raise RuntimeError('{} source tree {} does not exist'.format(name, source_path))

    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.pathsep.join([source_path] + sys.path)
    env['TEST'] = 'true'

    # Write out a config
    if settings_content is not None:
        settings_file = tmpdir_factory.mktemp(name).join('settings.py')
        settings_file.write(textwrap.dedent(settings_content))
        config_env_var = env_var_prefix + '_CONFIG'
        env[config_env_var] = settings_file.strpath

    subprocess_arguments = dict(env=env, cwd=source_path)

    # Create and populate the database
    if dbname:
        drop_and_create_database(dbname)
    if init_db_arguments:
        subprocess.check_call(init_db_arguments, **subprocess_arguments)

    # Start server
    with subprocess.Popen(start_server_arguments, **subprocess_arguments) as p:
        log.debug('Started %s server as pid %s', name, p.pid)
        wait_for_listen(port)

        yield 'http://localhost:{}/'.format(port)

        log.debug('Terminating %s server pid %s', name, p.pid)
        p.terminate()
        p.wait()


@pytest.yield_fixture(scope='session')
def resultsdb_server(tmpdir_factory):
    dbname = 'resultsdb_for_greenwave_functest'
    settings_content = """
        PORT = 5001
        SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2:///%s'
        DEBUG = False
        ADDITIONAL_RESULT_OUTCOMES = (
            'QUEUED',
            'RUNNING',
        )
        """ % dbname

    init_db_arguments = ['python3', 'run_cli.py', 'init_db']
    start_server_arguments = ['python3', 'runapp.py']

    with server_subprocess(
            name='resultsdb',
            port=5001,
            api_base='/api/v2.0',
            dbname=dbname,
            settings_content=settings_content,
            init_db_arguments=init_db_arguments,
            start_server_arguments=start_server_arguments,
            tmpdir_factory=tmpdir_factory) as url:
        yield url


@pytest.yield_fixture(scope='session')
def waiverdb_server(tmpdir_factory):
    dbname = 'waiverdb_for_greenwave_functest'
    settings_content = """
        AUTH_METHOD = 'dummy'
        DATABASE_URI = 'postgresql+psycopg2:///%s'
        MESSAGE_BUS_PUBLISH = False
        """ % dbname

    init_db_arguments = ['python3', os.path.join('waiverdb', 'manage.py'), 'db', 'upgrade']
    start_server_arguments = [
        'gunicorn-3',
        '--bind=127.0.0.1:5004',
        '--access-logfile=-',
        'waiverdb.wsgi:app']

    with server_subprocess(
            name='waiverdb',
            port=5004,
            dbname=dbname,
            settings_content=settings_content,
            init_db_arguments=init_db_arguments,
            start_server_arguments=start_server_arguments,
            tmpdir_factory=tmpdir_factory) as url:
        yield url


@pytest.yield_fixture(scope='session')
def distgit_server(tmpdir_factory):
    """ Creating a fake dist-git process. It is just a serving some files in a tmp dir """
    tmp_dir = tmpdir_factory.mktemp('distgit')
    f = open(tmp_dir.strpath + "/gating.yaml", "w+")
    f.close()

    start_server_arguments = [sys.executable, '-m', 'http.server', '5678']

    with server_subprocess(
            name='dist-git',
            port=5678,
            source_path=tmp_dir.strpath,
            start_server_arguments=start_server_arguments) as url:
        yield url


@pytest.yield_fixture(scope='session')
def cache_config(tmpdir_factory):
    cache_file = tmpdir_factory.mktemp('greenwave').join('cache.dbm')
    if 'GREENWAVE_TEST_URL' in os.environ:
        # This should point to the same cache as the Greenwave server used by tests.
        return {
            'backend': "dogpile.cache.memcached",
            'expiration_time': 300,
            'arguments': {
                'url': 'memcached:11211',
                'distributed_lock': True
            }
        }

    return {
        'backend': 'dogpile.cache.dbm',
        'expiration_time': 300,
        'arguments': {'filename': cache_file.strpath},
    }


@pytest.yield_fixture(scope='session')
def greenwave_server(tmpdir_factory, cache_config, resultsdb_server, waiverdb_server):
    settings_content = """
        CACHE = %s
        RESULTSDB_API_URL = '%sapi/v2.0'
        WAIVERDB_API_URL = '%sapi/v1.0'
        """ % (json.dumps(cache_config), resultsdb_server, waiverdb_server)

    start_server_arguments = [
        'gunicorn-3',
        '--bind=127.0.0.1:5005',
        '--access-logfile=-',
        'greenwave.wsgi:app']

    with server_subprocess(
            name='greenwave',
            port=5005,
            source_path='.',
            settings_content=settings_content,
            start_server_arguments=start_server_arguments,
            tmpdir_factory=tmpdir_factory) as url:
        yield url


@pytest.fixture(scope='session')
def requests_session(request):
    s = requests.Session()
    request.addfinalizer(s.close)
    return s


class TestDataBuilder(object):
    """
    Test fixture object which has helper methods for setting up test data in
    ResultsDB and WaiverDB.
    """

    def __init__(self, requests_session, resultsdb_url, waiverdb_url, distgit_url):
        self.requests_session = requests_session
        self.resultsdb_url = resultsdb_url
        self.waiverdb_url = waiverdb_url
        self.distgit_url = distgit_url
        self._counter = itertools.count(time.time())

    def unique_nvr(self, name='glibc', product_version='el7'):
        return '{}-1.0-{}.{}'.format(name, next(self._counter), product_version)

    def unique_compose_id(self):
        return 'Fedora-Rawhide-19700101.n.{}'.format(next(self._counter))

    def _create_result(self, data):
        response = self.requests_session.post(
            self.resultsdb_url + 'api/v2.0/results',
            timeout=TEST_HTTP_TIMEOUT,
            json=data
        )
        response.raise_for_status()
        return response.json()

    def create_compose_result(self, compose_id, testcase_name, outcome, scenario=None):
        data = {
            'testcase': {'name': testcase_name},
            'data': {'productmd.compose.id': compose_id},
            'outcome': outcome,
        }
        if scenario:
            data['data']['scenario'] = scenario
        return self._create_result(data)

    def create_rtt_compose_result(self, compose_id, outcome, variant, architecture):
        data = {
            'testcase': {'name': 'rtt.acceptance.validation'},
            'outcome': outcome,
            'data': {
                'productmd.compose.id': [compose_id],
                'system_variant': [variant],
                'system_architecture': [architecture],
            }
        }
        return self._create_result(data)

    def create_koji_build_result(self, nvr, testcase_name, outcome, type_='koji_build'):
        data = {
            'testcase': {'name': testcase_name},
            'outcome': outcome,
            'data': {'item': nvr, 'type': type_},
        }
        return self._create_result(data)

    def create_result(self, item, testcase_name, outcome,
                      scenario=None, key=None, _type='koji_build', **custom_data):
        data = {
            'testcase': {'name': testcase_name},
            'outcome': outcome,
        }
        if not key:
            data['data'] = {'item': item, 'type': _type}
        else:
            data['data'] = {key: item}
        if scenario:
            data['data']['scenario'] = scenario
        data['data'].update(custom_data)
        return self._create_result(data)

    def create_waiver(self, nvr, testcase_name, product_version, comment, waived=True,
                      subject_type='koji_build'):
        data = {
            'subject_type': subject_type,
            'subject_identifier': nvr,
            'testcase': testcase_name,
            'product_version': product_version,
            'waived': waived,
            'comment': comment
        }
        # We assume WaiverDB is configured with
        # AUTH_METHOD = 'dummy' to accept Basic with any credentials.
        response = self.requests_session.post(
            self.waiverdb_url + 'api/v1.0/waivers/',
            auth=('dummy', 'dummy'),
            timeout=TEST_HTTP_TIMEOUT,
            json=data
        )
        response.raise_for_status()
        return response.json()


@pytest.fixture(scope='session')
def testdatabuilder(requests_session, resultsdb_server, waiverdb_server, distgit_server):
    return TestDataBuilder(requests_session, resultsdb_server, waiverdb_server,
                           distgit_server)
