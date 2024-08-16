# SPDX-License-Identifier: GPL-2.0+

from textwrap import dedent
from unittest import mock

import pytest

import greenwave.consumers.resultsdb
from greenwave.app_factory import create_app
from greenwave.policies import Policy
from greenwave.product_versions import subject_product_versions
from greenwave.subjects.factory import create_subject

from .test_listeners import TestListenerAnnouncementSubject


@pytest.fixture(autouse=True)
def mock_retrieve_decision():
    with mock.patch("greenwave.decision.make_decision") as mocked:

        def retrieve_decision(data, config):
            # pylint: disable=unused-argument
            if "when" in data:
                return None
            return {}

        mocked.side_effect = retrieve_decision
        yield mocked


@pytest.fixture
def mock_retrieve_results():
    with mock.patch("greenwave.resources.ResultsRetriever.retrieve") as mocked:
        yield mocked


class TestConsumerAnnouncementSubject(TestListenerAnnouncementSubject):
    def announcement_subject(self, message):
        cls = greenwave.consumers.resultsdb.ResultsDBHandler

        app = create_app()
        with app.app_context():
            subject = cls.announcement_subject({"msg": message})
            if subject:
                return subject.to_dict()


def test_remote_rule_decision_change(
    mock_retrieve_yaml_remote_rule,
    mock_retrieve_scm_from_koji,
    mock_retrieve_results,
    koji_proxy,
):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"
    with mock.patch(publish) as mock_fedora_messaging:
        # gating.yaml
        gating_yaml = dedent("""
            --- !Policy
            product_versions: [fedora-rawhide, notexisting_prodversion]
            decision_context: test_context
            rules:
              - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
        """)
        mock_retrieve_yaml_remote_rule.return_value = gating_yaml

        policies = dedent("""
            --- !Policy
            id: test_policy
            product_versions: [fedora-rawhide]
            decision_context: test_context
            subject_type: koji_build
            rules:
              - !RemoteRule {}
        """)

        nvr = "nethack-1.2.3-1.rawhide"
        result = {
            "id": 1,
            "testcase": {"name": "dist.rpmdeplint"},
            "outcome": "PASSED",
            "data": {"item": nvr, "type": "koji_build"},
            "submit_time": "2019-03-25T16:34:41.882620",
        }
        mock_retrieve_results.return_value = [result]

        mock_retrieve_scm_from_koji.return_value = (
            "rpms",
            nvr,
            "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
        )

        message = {
            "body": {
                "topic": "resultsdb.result.new",
                "msg": {
                    "id": result["id"],
                    "outcome": "PASSED",
                    "testcase": {
                        "name": "dist.rpmdeplint",
                    },
                    "data": {
                        "item": [nvr],
                        "type": ["koji_build"],
                    },
                    "submit_time": "2019-03-25T16:34:41.882620",
                },
            }
        }
        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        assert len(mock_fedora_messaging.mock_calls) == 1

        mock_call = mock_fedora_messaging.mock_calls[0][1][0]
        assert mock_call.topic == "greenwave.decision.update"
        actual_msgs_sent = mock_call.body

        assert actual_msgs_sent == {
            "decision_context": "test_context",
            "product_version": "fedora-rawhide",
            "subject": [
                {"item": nvr, "type": "koji_build"},
            ],
            "subject_type": "koji_build",
            "subject_identifier": nvr,
            "previous": None,
        }


def test_remote_rule_decision_change_not_matching(
    mock_retrieve_yaml_remote_rule, mock_retrieve_scm_from_koji, mock_retrieve_results
):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"
    with mock.patch(publish) as mock_fedora_messaging:
        # gating.yaml
        gating_yaml = dedent("""
            --- !Policy
            product_versions: [fedora-rawhide]
            decision_context: test_context
            rules:
              - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
        """)
        mock_retrieve_yaml_remote_rule.return_value = gating_yaml

        policies = dedent("""
            --- !Policy
            id: test_policy
            product_versions: [fedora-rawhide]
            decision_context: another_test_context
            subject_type: koji_build
            rules:
              - !RemoteRule {}
        """)

        nvr = "nethack-1.2.3-1.rawhide"
        result = {
            "id": 1,
            "testcase": {"name": "dist.rpmdeplint"},
            "outcome": "PASSED",
            "data": {"item": nvr, "type": "koji_build"},
            "submit_time": "2019-03-25T16:34:41.882620",
        }
        mock_retrieve_results.return_value = [result]

        mock_retrieve_scm_from_koji.return_value = (
            "rpms",
            nvr,
            "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
        )

        message = {
            "body": {
                "topic": "resultsdb.result.new",
                "msg": {
                    "id": result["id"],
                    "outcome": "PASSED",
                    "testcase": {
                        "name": "dist.rpmdeplint",
                    },
                    "data": {
                        "item": [nvr],
                        "type": ["koji_build"],
                    },
                    "submit_time": "2019-03-25T16:34:41.882620",
                },
            }
        }
        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        assert len(mock_fedora_messaging.mock_calls) == 0


def test_guess_product_version():
    hub = mock.MagicMock()
    hub.config = {
        "environment": "environment",
        "topic_prefix": "topic_prefix",
    }
    handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)
    with handler.flask_app.app_context():
        subject = create_subject("koji_build", "release-e2e-test-1.0.1685-1.el5")
        product_versions = subject_product_versions(subject)
        assert product_versions == ["rhel-5"]

        subject = create_subject(
            "redhat-module", "rust-toolset-rhel8-20181010170614.b09eea91"
        )
        product_versions = subject_product_versions(subject)
        assert product_versions == ["rhel-8"]


def test_decision_change_for_modules(
    mock_retrieve_yaml_remote_rule, mock_retrieve_scm_from_koji, mock_retrieve_results
):
    """
    Test publishing decision change message for a module.
    """
    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"
    with mock.patch(publish) as mock_fedora_messaging:
        # gating.yaml
        gating_yaml = dedent("""
            --- !Policy
            product_versions:
              - rhel-8
            decision_context: osci_compose_gate_modules
            subject_type: redhat-module
            rules:
              - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-module.tier1.functional}
        """)
        mock_retrieve_yaml_remote_rule.return_value = gating_yaml

        policies = dedent("""
        --- !Policy
            id: "osci_compose_modules"
            product_versions:
              - rhel-8
            decision_context: osci_compose_gate_modules
            subject_type: redhat-module
            excluded_packages: []
            rules:
              - !RemoteRule {}
        """)

        nsvc = "python36-3.6-820181204160430.17efdbc7"
        result = {
            "id": 1,
            "testcase": {"name": "baseos-ci.redhat-module.tier1.functional"},
            "outcome": "PASSED",
            "data": {"item": nsvc, "type": "redhat-module"},
            "submit_time": "2019-03-25T16:34:41.882620",
        }
        mock_retrieve_results.return_value = [result]

        mock_retrieve_scm_from_koji.return_value = (
            "modules",
            nsvc,
            "97273b80dd568bd15f9636b695f6001ecadb65e0",
        )

        message = {
            "body": {
                "topic": "resultsdb.result.new",
                "msg": {
                    "id": result["id"],
                    "outcome": "PASSED",
                    "testcase": {
                        "name": "baseos-ci.redhat-module.tier1.functional",
                    },
                    "data": {
                        "item": [nsvc],
                        "type": ["redhat-module"],
                    },
                    "submit_time": "2019-03-25T16:34:41.882620",
                },
            }
        }
        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        assert len(mock_fedora_messaging.mock_calls) == 1

        mock_call = mock_fedora_messaging.mock_calls[0][1][0]
        assert mock_call.topic == "greenwave.decision.update"
        actual_msgs_sent = mock_call.body

        assert actual_msgs_sent == {
            "decision_context": "osci_compose_gate_modules",
            "product_version": "rhel-8",
            "subject": [
                {"item": nsvc, "type": "redhat-module"},
            ],
            "subject_type": "redhat-module",
            "subject_identifier": nsvc,
            "previous": None,
        }


def test_decision_change_for_composes(koji_proxy, mock_retrieve_results):
    """
    Test publishing decision change message for a compose.
    """
    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"
    with mock.patch(publish) as mock_fedora_messaging:
        policies = dedent("""
            --- !Policy
            id: "osci_rhel8_development_nightly_compose_gate"
            product_versions:
              - rhel-8
            decision_context: osci_rhel8_development_nightly_compose_gate
            subject_type: compose
            rules:
              - !PassingTestCaseRule {test_case_name: rtt.installability.validation}
              - !PassingTestCaseRule {test_case_name: rtt.beaker-acceptance.validation}
        """)

        result_data = {
            "item": ["RHEL-9000/unknown/x86_64"],
            "productmd.compose.id": ["RHEL-9000"],
            "type": ["compose"],
        }
        result = {
            "id": 1,
            "testcase": {"name": "rtt.installability.validation"},
            "outcome": "PASSED",
            "data": result_data,
            "submit_time": "2021-02-15T13:31:35.000001",
        }
        mock_retrieve_results.return_value = [result]

        koji_proxy.getBuild.return_value = None

        message = {
            "body": {
                "topic": "resultsdb.result.new",
                "msg": result,
            }
        }
        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        assert len(mock_fedora_messaging.mock_calls) == 1

        mock_call = mock_fedora_messaging.mock_calls[0][1][0]
        assert mock_call.topic == "greenwave.decision.update"
        actual_msgs_sent = mock_call.body

        assert actual_msgs_sent == {
            "decision_context": "osci_rhel8_development_nightly_compose_gate",
            "product_version": "rhel-8",
            "subject": [{"productmd.compose.id": "RHEL-9000"}],
            "subject_type": "compose",
            "subject_identifier": "RHEL-9000",
            "previous": None,
        }


def test_real_fedora_messaging_msg(mock_retrieve_results):
    message = {
        "msg": {
            "task": {
                "type": "bodhi_update",
                "item": "FEDORA-2019-9244c8b209",
                "name": "update.advisory_boot",
            },
            "result": {
                "id": 23523568,
                "submit_time": "2019-04-24 13:06:12 UTC",
                "prev_outcome": None,
                "outcome": "PASSED",
                "log_url": "https://openqa.stg.fedoraproject.org/tests/528801",
            },
        }
    }

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: update.advisory_boot}
    """)

    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"

    with mock.patch(publish) as mock_fedora_messaging:
        result = {
            "id": 1,
            "testcase": {"name": "dist.rpmdeplint"},
            "outcome": "PASSED",
            "data": {"item": "FEDORA-2019-9244c8b209", "type": "bodhi_update"},
            "submit_time": "2019-04-24 13:06:12.135146",
        }
        mock_retrieve_results.return_value = [result]

        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        handler.koji_base_url = None
        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        assert len(mock_fedora_messaging.mock_calls) == 1

        mock_call = mock_fedora_messaging.mock_calls[0][1][0]
        assert mock_call.topic == "greenwave.decision.update"
        actual_msgs_sent = mock_call.body

        assert actual_msgs_sent == {
            "decision_context": "test_context",
            "product_version": "fedora-rawhide",
            "subject": [
                {"item": "FEDORA-2019-9244c8b209", "type": "bodhi_update"},
            ],
            "subject_type": "bodhi_update",
            "subject_identifier": "FEDORA-2019-9244c8b209",
            "previous": None,
        }


def test_container_brew_build(mock_retrieve_results, koji_proxy):
    message = {
        "msg": {
            "submit_time": "2019-08-27T13:57:53.490376",
            "testcase": {
                "name": "example_test",
            },
            "data": {
                "brew_task_id": ["666"],
                "type": ["brew-build"],
                "item": ["example-container"],
            },
        }
    }

    policies = dedent("""
        --- !Policy
        id: test_policy
        product_versions: [example_product_version]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: example_test}
    """)

    publish = "greenwave.consumers.consumer.fedora_messaging.api.publish"

    with mock.patch(publish) as mock_fedora_messaging:
        result = {
            "id": 1,
            "testcase": {"name": "example_test"},
            "outcome": "PASSED",
            "data": {"item": "example-container", "type": "koji_build"},
            "submit_time": "2019-04-24 13:06:12.135146",
        }
        mock_retrieve_results.return_value = [result]

        hub = mock.MagicMock()
        hub.config = {
            "environment": "environment",
            "topic_prefix": "topic_prefix",
        }
        handler = greenwave.consumers.resultsdb.ResultsDBHandler(hub)

        koji_proxy.getBuild.return_value = None
        koji_proxy.getTaskRequest.return_value = [
            "git://example.com/project",
            "example_product_version",
            {},
        ]

        handler.flask_app.config["policies"] = Policy.safe_load_all(policies)
        with handler.flask_app.app_context():
            handler.consume(message)

        koji_proxy.getBuild.assert_not_called()
        koji_proxy.getTaskRequest.assert_called_once_with(666)

        assert len(mock_fedora_messaging.mock_calls) == 1

        mock_call = mock_fedora_messaging.mock_calls[0][1][0]
        assert mock_call.topic == "greenwave.decision.update"
        actual_msgs_sent = mock_call.body

        assert actual_msgs_sent == {
            "decision_context": "test_context",
            "product_version": "example_product_version",
            "subject": [
                {"item": "example-container", "type": "koji_build"},
            ],
            "subject_type": "koji_build",
            "subject_identifier": "example-container",
            "previous": None,
        }
