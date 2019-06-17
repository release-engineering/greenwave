# SPDX-License-Identifier: GPL-2.0+

import mock
import pytest

from textwrap import dedent

from greenwave.app_factory import create_app
from greenwave.policies import Policy

DEFAULT_DECISION_DATA = dict(
    decision_context='test_policies',
    product_version='fedora-rawhide',
    subject_type='koji_build',
    subject_identifier='nethack-1.2.3-1.f31',
)

DEFAULT_DECISION_POLICIES = """
    --- !Policy
    id: "test_policy"
    product_versions:
      - fedora-rawhide
    decision_context: test_policies
    subject_type: koji_build
    rules:
      - !PassingTestCaseRule {test_case_name: sometest}
"""


def make_result(outcome):
    return {
        'id': 123,
        'data': {
            'item': [DEFAULT_DECISION_DATA['subject_identifier']],
            'type': [DEFAULT_DECISION_DATA['subject_type']],
        },
        'testcase': {'name': 'sometest'},
        'outcome': outcome,
    }


@pytest.fixture
def mock_results():
    with mock.patch('greenwave.resources.ResultsRetriever.retrieve') as mocked:
        mocked.return_value = []
        yield mocked


@pytest.fixture
def mock_waivers():
    with mock.patch('greenwave.resources.WaiversRetriever.retrieve') as mocked:
        mocked.return_value = []
        yield mocked


def make_decision(**kwargs):
    app = create_app('greenwave.config.TestingConfig')
    app.config['policies'] = Policy.safe_load_all(dedent(DEFAULT_DECISION_POLICIES))
    client = app.test_client()
    data = DEFAULT_DECISION_DATA.copy()
    data.update(kwargs)
    return client.post('/api/v1.0/decision', json=data)


def test_make_decision_retrieves_waivers_on_missing(mock_results, mock_waivers):
    response = make_decision()
    assert 200 == response.status_code
    assert '1 of 1 required test results missing' == response.json['summary']
    mock_waivers.assert_called_once()


def test_make_decision_retrieves_waivers_on_failed(mock_results, mock_waivers):
    mock_results.return_value = [make_result(outcome='FAILED')]
    response = make_decision()
    assert 200 == response.status_code
    assert '1 of 1 required tests failed' == response.json['summary']
    mock_waivers.assert_called_once()


def test_make_decision_retrieves_waivers_omitted_on_passed(mock_results, mock_waivers):
    mock_results.return_value = [make_result(outcome='PASSED')]
    response = make_decision()
    assert 200 == response.status_code
    assert 'All required tests passed' == response.json['summary']
    mock_waivers.assert_not_called()


def test_make_decision_retrieves_waivers_once_on_verbose_and_missing(mock_results, mock_waivers):
    response = make_decision(verbose=True)
    assert 200 == response.status_code
    assert '1 of 1 required test results missing' == response.json['summary']
    mock_waivers.assert_called_once()
