# SPDX-License-Identifier: GPL-2.0+
from unittest.mock import Mock, patch

from pytest import fixture

from greenwave.app_factory import create_app


@fixture(autouse=True)
def mock_env_config(monkeypatch):
    monkeypatch.delenv("GREENWAVE_CONFIG", raising=False)


@fixture(autouse=True)
def set_environment_variable(monkeypatch):
    monkeypatch.setenv("TEST", "true")


@fixture
def app():
    app = create_app(config_obj="greenwave.config.TestingConfig")
    with app.app_context():
        yield app


@fixture
def client(app):
    yield app.test_client()


@fixture
def koji_proxy():
    mock_proxy = Mock()
    with patch("greenwave.resources.get_server_proxy", return_value=mock_proxy):
        yield mock_proxy
