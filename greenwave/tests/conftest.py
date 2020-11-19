import mock
import pytest

from greenwave.app_factory import create_app


@pytest.fixture(autouse=True)
def mock_env_config(monkeypatch):
    monkeypatch.delenv('GREENWAVE_CONFIG', raising=False)


@pytest.fixture
def app():
    app = create_app(config_obj='greenwave.config.TestingConfig')
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    yield app.test_client()


@pytest.fixture
def koji_proxy():
    mock_proxy = mock.Mock()
    with mock.patch('greenwave.resources.get_server_proxy', return_value=mock_proxy):
        yield mock_proxy
