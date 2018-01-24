# SPDX-License-Identifier: GPL-2.0+

import os
import itertools
import json
import threading
import socket
import wsgiref.simple_server
import pytest
import requests

import waiverdb.config
import waiverdb.app
import greenwave.app_factory


class WSGIServerThread(threading.Thread):

    def __init__(self, application, init_func, port):
        self._server = wsgiref.simple_server.make_server('127.0.0.1', port, application)
        self.init_func = init_func
        name = '{}-server-thread'.format(application.name)
        super(WSGIServerThread, self).__init__(name=name)

    def run(self):
        # We call the init_func *inside* our new thread, because when the
        # application is using a SQLite in-memory database with SQLAlchemy
        # each thread gets its own separate db. So initialising the database in
        # the main thread would not work.
        self.init_func()
        self._server.serve_forever()

    def stop(self):
        self._server.shutdown()
        self._server.socket.shutdown(socket.SHUT_RD)
        self._server.server_close()
        self.join()

    @property
    def url(self):
        host, port = self._server.server_address
        return 'http://{}:{}/'.format(host, port)


@pytest.fixture(scope='session')
def resultsdb_server(request):
    # Ideally ResultsDB would let us configure the app programmatically,
    # instead of doing everything globally at import time...
    os.environ['TEST'] = 'true'
    import resultsdb
    import resultsdb.cli
    del os.environ['TEST']
    app = resultsdb.app
    server = WSGIServerThread(
        app,
        init_func=lambda: resultsdb.cli.initialize_db(destructive=True),
        port=5001)
    server.start()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture(scope='session')
def waiverdb_server(request):
    class WaiverdbTestingConfig(waiverdb.config.TestingConfig):
        AUTH_METHOD = 'dummy'
        # As a workaround for https://github.com/mitsuhiko/flask-sqlalchemy/pull/364
        # WaiverDB patches flask_sqlalchemy.SignallingSession globally, which
        # messes up ResultsDB. So let's just turn off the messaging support in
        # WaiverDB entirely for now.
        MESSAGE_BUS_PUBLISH = False
    app = waiverdb.app.create_app(WaiverdbTestingConfig)
    server = WSGIServerThread(
        app,
        init_func=lambda: waiverdb.app.init_db(app),
        port=5004)
    server.start()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture(scope='session')
def greenwave_server(request):
    app = greenwave.app_factory.create_app('greenwave.config.TestingConfig')
    server = WSGIServerThread(app, init_func=lambda: None, port=app.config['PORT'])
    server.start()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture(scope='session')
def cached_greenwave_server(request):
    app = greenwave.app_factory.create_app('greenwave.config.CachedTestingConfig')
    server = WSGIServerThread(app, init_func=lambda: None, port=app.config['PORT'])
    server.start()
    request.addfinalizer(server.stop)
    try:
        yield server
    finally:
        # Remove the cache file so the next test can start afresh.
        os.remove(app.config['CACHE']['arguments']['filename'])


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

    def __init__(self, requests_session, resultsdb_url, waiverdb_url):
        self.requests_session = requests_session
        self.resultsdb_url = resultsdb_url
        self.waiverdb_url = waiverdb_url
        self._counter = itertools.count(1)

    def unique_nvr(self):
        return 'glibc-1.0-{}.el7'.format(self._counter.next())

    def unique_compose_id(self):
        return 'Fedora-9000-19700101.n.{}'.format(self._counter.next())

    def create_compose_result(self, compose_id, testcase_name, outcome, scenario=None):
        data = {
            'testcase': {'name': testcase_name},
            'data': {'productmd.compose.id': compose_id},
            'outcome': outcome,
        }
        if scenario:
            data['data']['scenario'] = scenario
        response = self.requests_session.post(
            self.resultsdb_url + 'api/v2.0/results',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    def create_result(self, item, testcase_name, outcome, scenario=None):
        data = {
            'testcase': {'name': testcase_name},
            'data': {'item': item, 'type': 'koji_build'},
            'outcome': outcome,
        }
        if scenario:
            data['data']['scenario'] = scenario
        response = self.requests_session.post(
            self.resultsdb_url + 'api/v2.0/results',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data))
        response.raise_for_status()
        return response.json()

    def create_waiver(self, result, product_version, waived=True):
        data = {
            'subject': result['subject'],
            'testcase': result['testcase'],
            'product_version': product_version,
            'waived': waived,
        }
        # We assume WaiverDB is configured with
        # AUTH_METHOD = 'dummy' to accept Basic with any credentials.
        response = self.requests_session.post(
            self.waiverdb_url + 'api/v1.0/waivers/',
            auth=('dummy', 'dummy'),
            headers={'Content-Type': 'application/json'},
            data=json.dumps(data))
        response.raise_for_status()
        return response.json()


@pytest.fixture(scope='session')
def testdatabuilder(requests_session, resultsdb_server, waiverdb_server):
    return TestDataBuilder(requests_session, resultsdb_server.url, waiverdb_server.url)
