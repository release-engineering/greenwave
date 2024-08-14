# SPDX-License-Identifier: GPL-2.0+

from textwrap import dedent
from unittest import mock

import pytest

from greenwave.app_factory import create_app
from greenwave.policies import Policy

DEFAULT_DECISION_DATA = dict(
    decision_context="test_policies",
    product_version="fedora-rawhide",
    subject_type="koji_build",
    subject_identifier="nethack-1.2.3-1.f31",
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
        "id": 123,
        "data": {
            "item": [DEFAULT_DECISION_DATA["subject_identifier"]],
            "type": [DEFAULT_DECISION_DATA["subject_type"]],
        },
        "testcase": {"name": "sometest"},
        "outcome": outcome,
    }


@pytest.fixture
def mock_results():
    with mock.patch("greenwave.resources.ResultsRetriever.retrieve") as mocked:
        mocked.return_value = []
        yield mocked


@pytest.fixture
def mock_waivers():
    with mock.patch("greenwave.resources.WaiversRetriever.retrieve") as mocked:
        mocked.return_value = []
        yield mocked


@pytest.fixture
def make_decision():
    app = create_app("greenwave.config.TestingConfig")

    def make_decision(policies=DEFAULT_DECISION_POLICIES, **kwargs):
        app.config["policies"] = Policy.safe_load_all(dedent(policies))
        client = app.test_client()
        data = DEFAULT_DECISION_DATA.copy()
        data.update(kwargs)
        return client.post("/api/v1.0/decision", json=data)

    yield make_decision


def test_make_decision_retrieves_waivers_on_missing(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    response = make_decision()
    assert 200 == response.status_code
    assert "Of 1 required test, 1 result missing" == response.json["summary"]
    mock_waivers.assert_called_once()


def test_make_decision_retrieves_waivers_on_failed(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = [make_result(outcome="FAILED")]
    mock_waivers.return_value = []
    response = make_decision()
    assert 200 == response.status_code
    assert "Of 1 required test, 1 test failed" == response.json["summary"]
    mock_waivers.assert_called_once()


def test_make_decision_retrieves_waivers_omitted_on_passed(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = [make_result(outcome="PASSED")]
    mock_waivers.return_value = []
    response = make_decision()
    assert 200 == response.status_code
    assert (
        "All required tests (1 total) have passed or been waived"
        == response.json["summary"]
    )
    mock_waivers.assert_not_called()


def test_make_decision_retrieves_waivers_on_errored(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = [make_result(outcome="ERROR")]
    mock_waivers.return_value = []
    response = make_decision()
    assert 200 == response.status_code
    assert "Of 1 required test, 1 test errored" == response.json["summary"]
    mock_waivers.assert_called_once()


def test_make_decision_retrieves_waivers_once_on_verbose_and_missing(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    response = make_decision(verbose=True)
    assert 200 == response.status_code
    assert "Of 1 required test, 1 result missing" == response.json["summary"]
    mock_waivers.assert_called_once()


def test_make_decision_with_no_tests_required(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_context: test_policies
        subject_type: koji_build
        rules: []
    """
    response = make_decision(policies=policies)
    assert 200 == response.status_code
    assert "No tests are required" == response.json["summary"]
    mock_waivers.assert_not_called()


def test_make_decision_with_no_tests_required_and_missing_gating_yaml(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_context: test_policies
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """
    with mock.patch("greenwave.resources.retrieve_scm_from_koji") as scm:
        scm.return_value = (
            "rpms",
            "nethack",
            "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
        )
        with mock.patch("greenwave.resources.retrieve_yaml_remote_rule") as f:
            f.return_value = None
            response = make_decision(policies=policies)
            assert 200 == response.status_code
            assert "No tests are required" == response.json["summary"]
            mock_waivers.assert_not_called()


@pytest.mark.parametrize(
    "remote_gating_yaml",
    (
        dedent("""
            --- !Policy
            decision_contexts:
            - test_policies
            - abc
            rules: [ ]
        """),
        dedent("""
            --- !Policy
            decision_contexts:
            - foo
            - bar
            rules: [ ]
        """),
    ),
)
def test_make_decision_with_no_tests_required_and_empty_remote_rules(
    mock_results, mock_waivers, make_decision, remote_gating_yaml
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_contexts:
          - test_policies
          - xyz
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """

    with mock.patch("greenwave.resources.retrieve_scm_from_koji") as scm:
        scm.return_value = (
            "rpms",
            "nethack",
            "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
        )
        with mock.patch("greenwave.resources.retrieve_yaml_remote_rule") as f:
            f.return_value = remote_gating_yaml
            response = make_decision(policies=policies)
            assert 200 == response.status_code
            assert "No tests are required" == response.json["summary"]
            mock_waivers.assert_not_called()


def test_make_decision_no_applicable_policies(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_contexts:
          - test_policies_2
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
    """
    response = make_decision(policies=policies)
    assert 404 == response.status_code
    assert response.json["message"] == (
        "Found no applicable policies for koji_build subjects at gating "
        "point(s) test_policies in fedora-rawhide"
    )
    mock_waivers.assert_not_called()


def test_make_decision_with_missing_required_gating_yaml(
    mock_results, mock_waivers, make_decision
):
    mock_results.return_value = []
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_context: test_policies
        subject_type: koji_build
        rules:
          - !RemoteRule {required: true}
    """
    with mock.patch("greenwave.resources.retrieve_scm_from_koji") as scm:
        scm.return_value = (
            "rpms",
            "nethack",
            "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
        )
        with mock.patch("greenwave.resources.retrieve_yaml_remote_rule") as f:
            f.return_value = None
            response = make_decision(policies=policies)
            assert 200 == response.status_code
            assert not response.json["policies_satisfied"]
            exp = "1 error due to missing remote rule file"
            assert exp == response.json["summary"]
            mock_waivers.assert_called_once()


def test_make_decision_multiple_contexts(mock_results, mock_waivers, make_decision):
    mock_results.return_value = [make_result(outcome="FAILED")]
    mock_waivers.return_value = []
    policies = """
        --- !Policy
        id: "test_policy"
        product_versions:
          - fedora-rawhide
        decision_context: test_policies
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}

        --- !Policy
        id: "test_policy_2"
        product_versions:
          - fedora-rawhide
        decision_context: test_2
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: sometest_2}

        --- !Policy
        id: "test_policy_3"
        product_versions:
          - fedora-rawhide
        decision_context: test_3
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: sometest_3}
    """
    response = make_decision(
        policies=policies, decision_context=["test_policies", "test_2"]
    )
    assert 200 == response.status_code
    assert "Of 2 required tests, 2 tests failed" == response.json["summary"]
    assert ["test_policy", "test_policy_2"] == response.json["applicable_policies"]
    mock_waivers.assert_called_once()


def test_subject_types(client):
    response = client.get("/api/v1.0/subject_types")
    assert response.status_code == 200
    data = response.json
    assert len(data["subject_types"])
    assert [x["id"] for x in data["subject_types"]] == [
        "bodhi_update",
        "compose",
        "koji_build",
        "redhat-container-image",
        "redhat-module",
    ]


def test_strict_trasport_security(client):
    response = client.get("/api/v1.0/version")
    sts = response.headers.get("Strict-Transport-Security")
    assert sts, response.headers
    assert "max-age" in sts
    assert "includeSubDomains" in sts
