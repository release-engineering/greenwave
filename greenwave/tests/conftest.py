# SPDX-License-Identifier: GPL-2.0+

import pytest
from greenwave.app_factory import create_app


@pytest.fixture(scope='session')
def app(request):
    app = create_app('greenwave.config.TestingConfig')
    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()

    def teardown():
        ctx.pop()

    request.addfinalizer(teardown)
    return app


@pytest.yield_fixture
def client(app):
    """A Flask test client. An instance of :class:`flask.testing.TestClient`
    by default.
    """
    with app.test_client() as client:
        yield client
