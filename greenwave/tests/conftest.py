# SPDX-License-Identifier: GPL-2.0+
from unittest.mock import Mock, patch

from pytest import fixture

from greenwave.app_factory import create_app

DUMMY_NVR = "nethack-1.2.3-1.rawhide"


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


@fixture
def mock_retrieve_scm_from_koji():
    with patch("greenwave.resources.retrieve_scm_from_koji") as mocked:
        yield mocked


@fixture
def mock_retrieve_yaml_remote_rule():
    with patch("greenwave.resources.retrieve_yaml_remote_rule") as mocked:
        yield mocked


@fixture
def mock_retrieve_results():
    with patch("greenwave.resources.ResultsRetriever.retrieve") as mocked:
        mocked.return_value = [
            {
                "id": 1,
                "testcase": {"name": "dist.rpmdeplint"},
                "outcome": "PASSED",
                "data": {"item": DUMMY_NVR, "type": "koji_build"},
                "submit_time": "2019-03-25T16:34:41.882620",
            }
        ]
        yield mocked


@fixture
def mock_retrieve_decision():
    with patch("greenwave.decision.make_decision") as mocked:

        def retrieve_decision(data, _config):
            if "when" in data:
                return {
                    "policies_satisfied": False,
                    "summary": "1 of 1 required test results missing",
                }
            return {
                "policies_satisfied": True,
                "summary": "All required tests passed",
            }

        mocked.side_effect = retrieve_decision
        yield mocked
