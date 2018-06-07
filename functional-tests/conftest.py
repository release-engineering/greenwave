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


@pytest.yield_fixture(scope='session')
def resultsdb_server(tmpdir_factory):
    if 'RESULTSDB_TEST_URL' in os.environ:
        yield os.environ['RESULTSDB_TEST_URL']
    else:
        # Start ResultsDB as a subprocess
        resultsdb_source = os.environ.get('RESULTSDB', '../resultsdb')
        if not os.path.isdir(resultsdb_source):
            raise RuntimeError('ResultsDB source tree %s does not exist' % resultsdb_source)
        dbname = 'resultsdb_for_greenwave_functest'
        # Write out a config
        settings_file = tmpdir_factory.mktemp('resultsdb').join('settings.py')
        settings_file.write(textwrap.dedent("""\
            PORT = 5001
            SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2:///%s'
            DEBUG = False
            """ % dbname))
        env = dict(os.environ,
                   PYTHONPATH=resultsdb_source,
                   RESULTSDB_CONFIG=settings_file.strpath)
        # Create and populate the database
        drop_and_create_database(dbname)
        subprocess.check_call(['python',
                               os.path.join(resultsdb_source, 'run_cli.py'),
                               'init_db'],
                              env=env)
        # Start server
        p = subprocess.Popen(['python',
                              os.path.join(resultsdb_source, 'runapp.py')],
                             env=env)
        log.debug('Started resultsdb server as pid %s', p.pid)
        wait_for_listen(5001)
        yield 'http://localhost:5001/'
        log.debug('Terminating resultsdb server pid %s', p.pid)
        p.terminate()
        p.wait()


@pytest.yield_fixture(scope='session')
def waiverdb_server(tmpdir_factory):
    if 'WAIVERDB_TEST_URL' in os.environ:
        yield os.environ['WAIVERDB_TEST_URL']
    else:
        # Start WaiverDB as a subprocess
        waiverdb_source = os.environ.get('WAIVERDB', '../waiverdb')
        if not os.path.isdir(waiverdb_source):
            raise RuntimeError('WaiverDB source tree %s does not exist' % waiverdb_source)
        dbname = 'waiverdb_for_greenwave_functest'
        # Write out a config
        settings_file = tmpdir_factory.mktemp('waiverdb').join('settings.py')
        settings_file.write(textwrap.dedent("""\
            AUTH_METHOD = 'dummy'
            DATABASE_URI = 'postgresql+psycopg2:///%s'
            """ % dbname))
        env = dict(os.environ,
                   PYTHONPATH=waiverdb_source,
                   WAIVERDB_CONFIG=settings_file.strpath)
        # Create and populate the database
        drop_and_create_database(dbname)
        subprocess.check_call(['python3',
                               os.path.join(waiverdb_source, 'waiverdb', 'manage.py'),
                               'db', 'upgrade'],
                              env=env)
        # Start server
        p = subprocess.Popen(['gunicorn-3',
                              '--bind=127.0.0.1:5004',
                              '--access-logfile=-',
                              'waiverdb.wsgi:app'],
                             env=env)
        log.debug('Started waiverdb server as pid %s', p.pid)
        wait_for_listen(5004)
        yield 'http://localhost:5004/'
        log.debug('Terminating waiverdb server pid %s', p.pid)
        p.terminate()
        p.wait()


@pytest.yield_fixture(scope='session')
def bodhi():
    if 'BODHI_TEST_URL' in os.environ:
        yield os.environ['BODHI_TEST_URL']
    else:
        # Start fake Bodhi as a subprocess
        p = subprocess.Popen(['gunicorn-3',
                              '--bind=127.0.0.1:5677',
                              '--access-logfile=-',
                              '--pythonpath=' + os.path.dirname(__file__),
                              'fake_bodhi:application'])
        log.debug('Started fake Bodhi as pid %s', p.pid)
        wait_for_listen(5677)
        yield 'http://localhost:5677/'
        log.debug('Terminating fake Bodhi pid %s', p.pid)
        p.terminate()
        p.wait()


@pytest.yield_fixture(scope='session')
def distgit_server(tmpdir_factory):
    """ Creating a fake dist-git process. It is just a serving some files in a tmp dir """
    tmp_dir = tmpdir_factory.mktemp('distgit')
    f = open(tmp_dir.strpath + "/gating.yaml", "w+")
    f.close()
    p = subprocess.Popen([sys.executable, '-m', 'http.server', '5678'], cwd=tmp_dir.strpath)
    log.debug('Started dist-git server as pid %s', p.pid)
    wait_for_listen(5678)
    yield 'http://localhost:5678'
    log.debug('Terminating dist-git server pid %s', p.pid)
    p.terminate()
    p.wait()


@pytest.yield_fixture(scope='session')
def greenwave_server(tmpdir_factory, resultsdb_server, waiverdb_server, bodhi):
    if 'GREENWAVE_TEST_URL' in os.environ:
        yield os.environ['GREENWAVE_TEST_URL']
    else:
        # Start Greenwave as a subprocess
        cache_file = tmpdir_factory.mktemp('greenwave').join('cache.dbm')
        settings_file = tmpdir_factory.mktemp('greenwave').join('settings.py')
        settings_file.write(textwrap.dedent("""\
            CACHE = {
                'backend': 'dogpile.cache.dbm',
                'expiration_time': 300,
                'arguments': {'filename': %r},
            }
            RESULTSDB_API_URL = '%sapi/v2.0'
            WAIVERDB_API_URL = '%sapi/v1.0'
            BODHI_URL = %r
            """ % (cache_file.strpath, resultsdb_server, waiverdb_server, bodhi)))

        # We also update the config file for *this* process, as well as the server subprocess,
        # because the fedmsg consumer tests actually invoke the handler code in-process.
        # This way they will see the same config as the server.
        os.environ['GREENWAVE_CONFIG'] = settings_file.strpath

        env = dict(os.environ,
                   PYTHONPATH='.',
                   GREENWAVE_CONFIG=settings_file.strpath)
        p = subprocess.Popen(['gunicorn-3',
                              '--bind=127.0.0.1:5005',
                              '--access-logfile=-',
                              'greenwave.wsgi:app'],
                             env=env)
        log.debug('Started greenwave server as pid %s', p.pid)
        wait_for_listen(5005)
        yield 'http://localhost:5005/'
        log.debug('Terminating greenwave server pid %s', p.pid)
        p.terminate()
        p.wait()


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

    def __init__(self, requests_session, resultsdb_url, waiverdb_url, bodhi_url, distgit_url):
        self.requests_session = requests_session
        self.resultsdb_url = resultsdb_url
        self.waiverdb_url = waiverdb_url
        self.bodhi_url = bodhi_url
        self.distgit_url = distgit_url
        self._counter = itertools.count(1)

    def unique_nvr(self, name='glibc'):
        return '{}-1.0-{}.el7'.format(name, next(self._counter))

    def unique_compose_id(self):
        return 'Fedora-9000-19700101.n.{}'.format(next(self._counter))

    def _create_result(self, data):
        response = self.requests_session.post(
            self.resultsdb_url + 'api/v2.0/results',
            headers={'Content-Type': 'application/json'},
            timeout=TEST_HTTP_TIMEOUT,
            data=json.dumps(data))
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

    def create_koji_build_result(self, nvr, testcase_name, outcome, type_='koji_build'):
        data = {
            'testcase': {'name': testcase_name},
            'outcome': outcome,
            'data': {'item': nvr, 'type': type_},
        }
        return self._create_result(data)

    def create_result(self, item, testcase_name, outcome, scenario=None, key=None):
        data = {
            'testcase': {'name': testcase_name},
            'outcome': outcome,
        }
        if not key:
            data['data'] = {'item': item, 'type': 'koji_build'}
        else:
            data['data'] = {key: item}
        if scenario:
            data['data']['scenario'] = scenario
        return self._create_result(data)

    def create_waiver(self, nvr, testcase_name, product_version, comment, waived=True):
        data = {
            'subject_type': 'koji_build',
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
            headers={'Content-Type': 'application/json'},
            timeout=TEST_HTTP_TIMEOUT,
            data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    def create_bodhi_update(self, build_nvrs):
        data = {'builds': [{'nvr': nvr} for nvr in build_nvrs]}
        response = self.requests_session.post(
            self.bodhi_url + 'updates/',
            headers={'Content-Type': 'application/json'},
            timeout=TEST_HTTP_TIMEOUT,
            data=json.dumps(data))
        response.raise_for_status()
        return response.json()


@pytest.fixture(scope='session')
def testdatabuilder(requests_session, resultsdb_server, waiverdb_server, bodhi, distgit_server):
    return TestDataBuilder(requests_session, resultsdb_server, waiverdb_server, bodhi,
                           distgit_server)
