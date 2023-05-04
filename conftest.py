# SPDX-License-Identifier: GPL-2.0+
import mock
import pytest


@pytest.fixture(autouse=True)
def set_environment_variable(monkeypatch):
    monkeypatch.setenv('TEST', 'true')


@pytest.fixture
def koji_proxy():
    mock_proxy = mock.Mock()
    with mock.patch('greenwave.resources.get_server_proxy', return_value=mock_proxy):
        yield mock_proxy
