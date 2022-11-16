# SPDX-License-Identifier: GPL-2.0+
import json
from textwrap import dedent

import mock
import pytest
import stomp
from requests.exceptions import HTTPError

from greenwave.app_factory import create_app
from greenwave.listeners.waiverdb import WaiverDBListener
from greenwave.listeners.resultsdb import ResultsDBListener
from greenwave.monitor import (
    messaging_rx_counter,
    messaging_rx_ignored_counter,
)
from greenwave.policies import Policy
from greenwave.product_versions import subject_product_version
from greenwave.subjects.factory import create_subject

DECISION_UPDATE_TOPIC = "/topic/VirtualTopic.eng.greenwave.decision.update"
RESULTSDB_QUEUE = (
    "/queue/Consumer.client-greenwave.dev-resultsdb"
    ".VirtualTopic.eng.resultsdb.result.new"
)
WAIVERDB_QUEUE = (
    "/queue/Consumer.client-greenwave.dev-waiverdb"
    ".VirtualTopic.eng.waiverdb.waiver.new"
)
CONFIG_NAME = "greenwave.config.TestingConfig"

POLICIES_DEFAULT = dedent(
    """
    --- !Policy
    id: test_policy
    product_versions: [fedora-rawhide]
    decision_context: test_context
    subject_type: koji_build
    rules:
      - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
"""
)

POLICIES_WITH_REMOTE_RULE = dedent(
    """
    --- !Policy
    id: test_policy
    product_versions: [fedora-rawhide]
    decision_context: test_context
    subject_type: koji_build
    rules:
      - !RemoteRule {}
"""
)

DUMMY_NVR = "nethack-1.2.3-1.rawhide"


class DummyMessage:
    headers = {"message-id": "dummy-message"}

    def __init__(
        self,
        outcome="PASSED",
        nvr=DUMMY_NVR,
        type_="koji_build",
        testcase="dist.rpmdeplint",
        **kwargs
    ):
        if "message" in kwargs:
            self.message = kwargs["message"]
            del kwargs["message"]
        else:
            self.message = {
                "id": 1,
                "outcome": outcome,
                "testcase": {
                    "name": testcase,
                },
                "data": {
                    "item": [nvr],
                    "type": [type_],
                },
                "submit_time": "2019-03-25T16:34:41.882620",
            }
        self.message.update(kwargs)

    @property
    def body(self):
        return json.dumps(self.message)


def resultsdb_listener(policies=POLICIES_DEFAULT):
    listener = ResultsDBListener(config_obj=CONFIG_NAME)
    listener.app.config["policies"] = Policy.safe_load_all(policies)
    listener.listen()
    listener.on_connected(frame=mock.Mock())
    return listener


def waiverdb_listener():
    listener = WaiverDBListener(config_obj=CONFIG_NAME)
    listener.listen()
    listener.on_connected(frame=mock.Mock())
    return listener


@pytest.fixture(autouse=True)
def mock_retrieve_decision():
    with mock.patch("greenwave.decision.make_decision") as mocked:

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


@pytest.fixture
def mock_retrieve_results():
    with mock.patch("greenwave.resources.ResultsRetriever.retrieve") as mocked:
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


@pytest.fixture
def mock_retrieve_scm_from_koji():
    with mock.patch("greenwave.resources.retrieve_scm_from_koji") as mocked:
        yield mocked


@pytest.fixture
def mock_retrieve_yaml_remote_rule():
    with mock.patch("greenwave.resources.retrieve_yaml_remote_rule") as mocked:
        yield mocked


@pytest.fixture
def mock_connection():
    with mock.patch(
        "greenwave.listeners.base.stomp.connect.StompConnection11"
    ) as connection:
        connection().is_connected.side_effect = [False, True]
        yield connection()


def announcement_subject(message):
    app = create_app(config_obj=CONFIG_NAME)
    with app.app_context():
        subject = ResultsDBListener.announcement_subject(message)
        if subject:
            return subject.to_dict()


def test_announcement_keys_decode_with_list():
    message = {
        "data": {
            "original_spec_nvr": ["glibc-1.0-1.fc27"],
        }
    }
    assert announcement_subject(message) == {
        "type": "koji_build",
        "item": "glibc-1.0-1.fc27",
    }


def test_no_announcement_subjects_for_empty_nvr():
    """The CI pipeline submits a lot of results for the test
    'org.centos.prod.ci.pipeline.allpackages-build.package.ignored'
    with the 'original_spec_nvr' key present, but the value just an
    empty string. To avoid unpredictable consequences, we should not
    return any announcement subjects for such a message.
    """
    message = {
        "data": {
            "original_spec_nvr": [""],
        }
    }

    assert announcement_subject(message) is None


def test_announcement_subjects_for_brew_build():
    # The 'brew-build' type appears internally within Red Hat. We treat it as an
    # alias of 'koji_build'.
    message = {
        "data": {
            "type": "brew-build",
            "item": ["glibc-1.0-3.fc27"],
        }
    }

    assert announcement_subject(message) == {
        "type": "koji_build",
        "item": "glibc-1.0-3.fc27",
    }


def test_announcement_subjects_for_new_compose_message():
    """Ensure we are producing the right subjects for compose decisions
    as this has caused a lot of confusion in the past. The only
    reliable way to make a compose decision is by looking for the key
    productmd.compose.id with value of the compose ID. This is only
    possible with new-style 'resultsdb' message, like this one.
    """
    message = {
        "data": {
            "scenario": ["fedora.universal.x86_64.64bit"],
            "source": ["openqa"],
            "productmd.compose.name": ["Fedora"],
            "firmware": ["bios"],
            "meta.conventions": ["result productmd.compose fedora.compose"],
            "productmd.compose.respin": ["0"],
            "item": ["Fedora-Rawhide-20181205.n.0"],
            "productmd.compose.id": ["Fedora-Rawhide-20181205.n.0"],
            "type": ["compose"],
            "productmd.compose.date": ["20181205"],
            "productmd.compose.version": ["Rawhide"],
            "arch": ["x86_64"],
            "productmd.compose.type": ["nightly"],
            "productmd.compose.short": ["Fedora"],
        }
    }

    assert announcement_subject(message) == {
        "productmd.compose.id": "Fedora-Rawhide-20181205.n.0"
    }


def test_no_announcement_subjects_for_old_compose_message():
    """With an old-style 'taskotron' message like this one, it is not
    possible to reliably make a compose decision - see
    https://pagure.io/greenwave/issue/122 etc. So we should NOT
    produce any subjects for this kind of message.
    """
    message = {
        "task": {
            "item": "Fedora-AtomicHost-28_Update-20180723.1839.x86_64.qcow2",
            "type": "compose",
            "name": "compose.install_no_user",
        },
        "result": {
            "prev_outcome": None,
            "outcome": "PASSED",
            "id": 23004689,
            "submit_time": "2018-07-23 21:07:38 UTC",
            "log_url": "https://apps.fedoraproject.org/autocloud/jobs/9238/output",
        },
    }

    assert announcement_subject(message) is None


@pytest.mark.parametrize(
    "old_decision, new_decision",
    (
        (
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 1, "type": "test-result-missing"}
                ],
                "summary": "1 of 1 required test results missing",
            },
            {
                "policies_satisfied": True,
                "satisfied_requirements": [
                    {"result_id": 1, "type": "test-result-missing-waived"}
                ],
                "unsatisfied_requirements": [],
                "summary": "All required tests passed",
            },
        ),
        (
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 1, "type": "test-result-missing", "scenario": "A"}
                ],
                "summary": "1 of 1 required test results missing",
            },
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 1, "type": "test-result-missing", "scenario": "A"},
                    {"result_id": 2, "type": "test-result-missing", "scenario": "B"},
                ],
                "summary": "2 of 2 required test results missing",
            },
        ),
        (
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 1, "type": "test-result-missing"}
                ],
                "summary": "1 of 1 required test results missing",
            },
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 2, "type": "test-result-failed"}
                ],
                "summary": "1 of 1 required tests failed",
            },
        ),
    ),
)
def test_decision_changes(
    mock_retrieve_decision,
    mock_retrieve_results,
    mock_connection,
    old_decision,
    new_decision,
):
    """
    Test publishing decision changes with given previous decision.
    """

    def retrieve_decision(data, _config):
        if "when" in data:
            return old_decision
        return new_decision

    mock_retrieve_decision.side_effect = retrieve_decision

    listener = resultsdb_listener()

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    expected_message = {
        "decision_context": "test_context",
        "product_version": "fedora-rawhide",
        "subject": [
            {"item": DUMMY_NVR, "type": "koji_build"},
        ],
        "subject_type": "koji_build",
        "subject_identifier": DUMMY_NVR,
        "previous": old_decision,
    }
    expected_message.update(new_decision)
    expected_body = {"msg": expected_message, "topic": DECISION_UPDATE_TOPIC}
    assert json.loads(mock_call["body"]) == expected_body
    expected_headers = {
        k: expected_message[k] for k in (
            "subject_type",
            "subject_identifier",
            "product_version",
            "decision_context",
            "summary",
        )
    }
    expected_headers["policies_satisfied"] = str(expected_message["policies_satisfied"]).lower()
    assert mock_call["headers"] == expected_headers


@pytest.mark.parametrize(
    "old_decision, new_decision",
    (
        (
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 1, "type": "test-result-failed"}
                ],
            },
            {
                "policies_satisfied": False,
                "satisfied_requirements": [],
                "unsatisfied_requirements": [
                    {"result_id": 2, "type": "test-result-failed"}
                ],
            },
        ),
        (
            HTTPError(),
            {"policies_satisfied": True},
        ),
    ),
)
def test_decision_does_not_change(
    mock_retrieve_decision,
    mock_retrieve_results,
    mock_connection,
    old_decision,
    new_decision,
):
    """
    Test not publishing decision changes with given previous decision.
    """

    def retrieve_decision(data, _config):
        if "when" in data:
            if isinstance(old_decision, Exception):
                raise old_decision
            return old_decision
        return new_decision

    mock_retrieve_decision.side_effect = retrieve_decision

    listener = resultsdb_listener()

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.send.mock_calls) == 0


@pytest.mark.parametrize("outcome", ("QUEUED", "RUNNING"))
def test_decision_does_not_change_on_incomplete_outcome(
    mock_retrieve_decision,
    mock_retrieve_results,
    mock_connection,
    outcome,
):
    """
    Test not publishing decision changes with given previous decision.
    """
    listener = resultsdb_listener()

    with listener.app.app_context():
        listener.on_message(DummyMessage(outcome=outcome))

    assert len(mock_connection.send.mock_calls) == 0
    assert len(mock_retrieve_decision.mock_calls) == 0
    assert len(mock_retrieve_results.mock_calls) == 0


def test_decision_does_not_change_on_invalid_subject_id(
    mock_retrieve_decision,
    mock_retrieve_results,
    mock_connection,
):
    """
    Test not publishing decision changes for invalid subject ID.
    """
    listener = resultsdb_listener()

    with listener.app.app_context():
        listener.on_message(DummyMessage(nvr="", type_="magic-build"))

    assert len(mock_connection.send.mock_calls) == 0
    assert len(mock_retrieve_decision.mock_calls) == 0
    assert len(mock_retrieve_results.mock_calls) == 0


def test_remote_rule_decision_change(
    mock_retrieve_yaml_remote_rule,
    mock_retrieve_scm_from_koji,
    mock_retrieve_results,
    mock_connection,
):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    gating_yaml = dedent(
        """
        --- !Policy
        product_versions: [fedora-rawhide, notexisting_prodversion]
        decision_context: test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """
    )
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    mock_retrieve_scm_from_koji.return_value = (
        "rpms",
        DUMMY_NVR,
        "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
    )

    listener = resultsdb_listener(POLICIES_WITH_REMOTE_RULE)

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "test_context",
            "product_version": "fedora-rawhide",
            "subject": [
                {"item": DUMMY_NVR, "type": "koji_build"},
            ],
            "subject_type": "koji_build",
            "subject_identifier": DUMMY_NVR,
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "koji_build",
        "subject_identifier": DUMMY_NVR,
        "product_version": "fedora-rawhide",
        "decision_context": "test_context",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_remote_rule_decision_change_not_matching(
    mock_retrieve_yaml_remote_rule,
    mock_retrieve_scm_from_koji,
    mock_retrieve_results,
    mock_connection,
):
    """
    Test publishing decision change message for test cases mentioned in
    gating.yaml.
    """
    gating_yaml = dedent(
        """
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_context: another_test_context
        rules:
          - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
    """
    )
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    mock_retrieve_scm_from_koji.return_value = (
        "rpms",
        DUMMY_NVR,
        "c3c47a08a66451cb9686c49f040776ed35a0d1bb",
    )

    listener = resultsdb_listener(POLICIES_WITH_REMOTE_RULE)

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.send.mock_calls) == 0


@pytest.mark.parametrize("enabled", (True, False))
def test_decision_change_toggle(
    mock_retrieve_decision,
    mock_retrieve_results,
    mock_connection,
    enabled,
):
    """
    Test we do not publish a decision change when the config setting
    is False, even if we otherwise would.
    """
    old_decision = {
        "policies_satisfied": False,
        "satisfied_requirements": [],
        "unsatisfied_requirements": [
            {"result_id": 1, "type": "test-result-missing"}
        ],
        "summary": "1 of 1 required test results missing",
    }
    new_decision = {
        "policies_satisfied": True,
        "satisfied_requirements": [
            {"result_id": 1, "type": "test-result-missing-waived"}
        ],
        "unsatisfied_requirements": [],
        "summary": "All required tests passed",
    }

    def retrieve_decision(data, _config):
        if "when" in data:
            return old_decision
        return new_decision

    mock_retrieve_decision.side_effect = retrieve_decision

    listener = resultsdb_listener()
    listener.app.config["PUBLISH_DECISION_UPDATES"] = enabled
    with listener.app.app_context():
        listener.on_message(DummyMessage())

    if enabled:
        assert len(mock_connection.send.mock_calls) == 1
        mock_call = mock_connection.send.mock_calls[0][2]
        assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    else:
        assert len(mock_connection.send.mock_calls) == 0


def test_guess_product_version(mock_connection):
    listener = resultsdb_listener()

    with listener.app.app_context():
        subject = create_subject("koji_build", "release-e2e-test-1.0.1685-1.el5")
        product_version = subject_product_version(subject)
        assert product_version == "rhel-5"

        subject = create_subject(
            "redhat-module", "rust-toolset-rhel8-20181010170614.b09eea91"
        )
        product_version = subject_product_version(subject)
        assert product_version == "rhel-8"


def test_guess_product_version_with_koji(koji_proxy, app):
    koji_proxy.getBuild.return_value = {"task_id": 666}
    koji_proxy.getTaskRequest.return_value = [
        "git://example.com/project",
        "rawhide",
        {},
    ]

    subject = create_subject("container-build", "fake_koji_build")
    product_version = subject_product_version(subject, "http://localhost:5006/kojihub")

    koji_proxy.getBuild.assert_called_once_with("fake_koji_build")
    koji_proxy.getTaskRequest.assert_called_once_with(666)
    assert product_version == "fedora-rawhide"


def test_guess_product_version_with_koji_without_task_id(koji_proxy, app):
    koji_proxy.getBuild.return_value = {"task_id": None}

    subject = create_subject("container-build", "fake_koji_build")
    product_version = subject_product_version(subject, "http://localhost:5006/kojihub")

    koji_proxy.getBuild.assert_called_once_with("fake_koji_build")
    koji_proxy.getTaskRequest.assert_not_called()
    assert product_version is None


@pytest.mark.parametrize(
    "task_request",
    (
        ["git://example.com/project", 7777, {}],
        [],
        None,
    ),
)
def test_guess_product_version_with_koji_and_unexpected_task_type(
    task_request, koji_proxy, app
):
    koji_proxy.getBuild.return_value = {"task_id": 666}
    koji_proxy.getTaskRequest.return_value = task_request

    subject = create_subject("container-build", "fake_koji_build")
    product_version = subject_product_version(subject, "http://localhost:5006/kojihub")

    koji_proxy.getBuild.assert_called_once_with("fake_koji_build")
    koji_proxy.getTaskRequest.assert_called_once_with(666)
    assert product_version is None


@pytest.mark.parametrize(
    "nvr",
    (
        "badnvr.elastic-1-228",
        "badnvr-1.2-1.elastic8",
        "el99",
        "badnvr-1.2.f30",
    ),
)
def test_guess_product_version_failure(nvr):
    app = create_app(config_obj=CONFIG_NAME)
    with app.app_context():
        subject = create_subject("koji_build", nvr)
    product_version = subject_product_version(subject)
    assert product_version is None


def test_decision_change_for_modules(
    mock_retrieve_yaml_remote_rule,
    mock_retrieve_scm_from_koji,
    mock_retrieve_results,
    mock_connection,
):
    """
    Test publishing decision change message for a module.
    """
    gating_yaml = dedent(
        """
        --- !Policy
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate_modules
        subject_type: redhat-module
        rules:
          - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-module.tier1.functional}
    """
    )
    mock_retrieve_yaml_remote_rule.return_value = gating_yaml

    policies = dedent(
        """
    --- !Policy
        id: "osci_compose_modules"
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate_modules
        subject_type: redhat-module
        excluded_packages: []
        rules:
          - !RemoteRule {}
    """
    )

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

    message = DummyMessage(
        outcome="PASSED",
        testcase="baseos-ci.redhat-module.tier1.functional",
        nvr=nsvc,
        type_="redhat-module",
    )
    listener = resultsdb_listener()

    listener.app.config["policies"] = Policy.safe_load_all(policies)
    with listener.app.app_context():
        listener.on_message(message)

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "osci_compose_gate_modules",
            "product_version": "rhel-8",
            "subject": [
                {"item": nsvc, "type": "redhat-module"},
            ],
            "subject_type": "redhat-module",
            "subject_identifier": nsvc,
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "redhat-module",
        "subject_identifier": nsvc,
        "product_version": "rhel-8",
        "decision_context": "osci_compose_gate_modules",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_decision_change_for_composes(
    koji_proxy, mock_retrieve_results, mock_connection
):
    """
    Test publishing decision change message for a compose.
    """
    policies = dedent(
        """
        --- !Policy
        id: "osci_rhel8_development_nightly_compose_gate"
        product_versions:
          - rhel-8
        decision_context: osci_rhel8_development_nightly_compose_gate
        subject_type: compose
        rules:
          - !PassingTestCaseRule {test_case_name: rtt.installability.validation}
          - !PassingTestCaseRule {test_case_name: rtt.beaker-acceptance.validation}
    """
    )

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

    message = DummyMessage(
        testcase="rtt.installability.validation",
        data=result_data,
    )

    koji_proxy.getBuild.return_value = None

    listener = resultsdb_listener()

    listener.app.config["policies"] = Policy.safe_load_all(policies)
    with listener.app.app_context():
        listener.on_message(message)

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "osci_rhel8_development_nightly_compose_gate",
            "product_version": "rhel-8",
            "subject": [{"productmd.compose.id": "RHEL-9000"}],
            "subject_type": "compose",
            "subject_identifier": "RHEL-9000",
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "compose",
        "subject_identifier": "RHEL-9000",
        "product_version": "rhel-8",
        "decision_context": "osci_rhel8_development_nightly_compose_gate",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_fake_fedora_messaging_msg(mock_retrieve_results, mock_connection):
    message = {
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

    result = {
        "data": {
            "arch": ["x86_64"],
            "firmware": ["bios"],
            "item": ["FEDORA-2019-9244c8b209"],
            "meta.conventions": ["result fedora.bodhi"],
            "scenario": ["fedora.updates-server.x86_64.64bit"],
            "source": ["openqa"],
            "type": ["bodhi_update"],
        },
        "groups": [
            "61d11797-79cd-579f-b150-349cc77e0941",
            "222c442c-5d94-528f-9b9e-3fb379edf657",
            "0f3309ea-6d4c-59b2-b422-d73e9b8511f3",
        ],
        "href": "https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0/results/23523568",
        "id": 23523568,
        "note": "",
        "outcome": "PASSED",
        "ref_url": "https://openqa.stg.fedoraproject.org/tests/528801",
        "submit_time": "2019-04-24T13:06:12.135146",
        "testcase": {
            "href": "https://taskotron.stg.fedoraproject.org/resultsdb_api/api/v2.0/testcases/update.advisory_boot",  # noqa
            "name": "update.advisory_boot",
            "ref_url": "https://openqa.stg.fedoraproject.org/tests/546627",
        },
    }

    policies = dedent(
        """
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: update.advisory_boot}
    """
    )

    result = {
        "id": 1,
        "testcase": {"name": "dist.rpmdeplint"},
        "outcome": "PASSED",
        "data": {"item": "FEDORA-2019-9244c8b209", "type": "bodhi_update"},
        "submit_time": "2019-04-24 13:06:12.135146",
    }
    mock_retrieve_results.return_value = [result]

    listener = resultsdb_listener()

    listener.koji_base_url = None
    listener.app.config["policies"] = Policy.safe_load_all(policies)
    with listener.app.app_context():
        listener.on_message(DummyMessage(message=message))

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "test_context",
            "product_version": "fedora-rawhide",
            "subject": [
                {"item": "FEDORA-2019-9244c8b209", "type": "bodhi_update"},
            ],
            "subject_type": "bodhi_update",
            "subject_identifier": "FEDORA-2019-9244c8b209",
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "bodhi_update",
        "subject_identifier": "FEDORA-2019-9244c8b209",
        "product_version": "fedora-rawhide",
        "decision_context": "test_context",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_container_brew_build(mock_retrieve_results, koji_proxy, mock_connection):
    message = {
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

    policies = dedent(
        """
        --- !Policy
        id: test_policy
        product_versions: [example_product_version]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: example_test}
    """
    )

    result = {
        "id": 1,
        "testcase": {"name": "example_test"},
        "outcome": "PASSED",
        "data": {"item": "example-container", "type": "koji_build"},
        "submit_time": "2019-04-24 13:06:12.135146",
    }
    mock_retrieve_results.return_value = [result]

    listener = resultsdb_listener(policies)

    koji_proxy.getBuild.return_value = None
    koji_proxy.getTaskRequest.return_value = [
        "git://example.com/project",
        "example_product_version",
        {},
    ]

    with listener.app.app_context():
        listener.on_message(DummyMessage(message=message))

    koji_proxy.getBuild.assert_not_called()
    koji_proxy.getTaskRequest.assert_called_once_with(666)

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "test_context",
            "product_version": "example_product_version",
            "subject": [
                {"item": "example-container", "type": "koji_build"},
            ],
            "subject_type": "koji_build",
            "subject_identifier": "example-container",
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "koji_build",
        "subject_identifier": "example-container",
        "product_version": "example_product_version",
        "decision_context": "test_context",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_waiverdb_message(mock_connection):
    waiver = dict(
        subject_identifier=DUMMY_NVR,
        subject_type="koji_build",
        testcase="example_test",
        product_version="rawhide",
        comment="waived for tests",
        timestamp="2019-04-24T13:07:00.000000",
    )

    policies = dedent(
        """
        --- !Policy
        id: test_policy
        product_versions: [rawhide]
        decision_context: test_context
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: example_test}
    """
    )

    listener = waiverdb_listener()

    listener.app.config["policies"] = Policy.safe_load_all(policies)
    with listener.app.app_context():
        listener.on_message(DummyMessage(message=waiver))

    assert len(mock_connection.send.mock_calls) == 1
    mock_call = mock_connection.send.mock_calls[0][2]
    assert mock_call["destination"] == DECISION_UPDATE_TOPIC
    assert json.loads(mock_call["body"]) == {
        "msg": {
            "decision_context": "test_context",
            "product_version": "rawhide",
            "subject": [
                {"item": DUMMY_NVR, "type": "koji_build"},
            ],
            "subject_type": "koji_build",
            "subject_identifier": DUMMY_NVR,
            "testcase": "example_test",
            "policies_satisfied": True,
            "previous": {
                "policies_satisfied": False,
                "summary": "1 of 1 required test results missing",
            },
            "summary": "All required tests passed",
        },
        # Duplication of the topic in the body for datanommer, for message backwards compat
        "topic": DECISION_UPDATE_TOPIC,
    }
    assert mock_call["headers"] == {
        "subject_type": "koji_build",
        "subject_identifier": DUMMY_NVR,
        "product_version": "rawhide",
        "decision_context": "test_context",
        "policies_satisfied": "true",
        "summary": "All required tests passed",
    }


def test_listener_resultsdb_subscribe_after_connect(mock_connection):
    """
    Test subscribed to resultsdb after connected.
    """
    listener = resultsdb_listener()
    assert len(mock_connection.connect.mock_calls) == 1
    mock_connection.subscribe.assert_called_once_with(
        destination=RESULTSDB_QUEUE,
        id=listener.uid,
        ack="client-individual",
    )


def test_listener_waiverdb_subscribe_after_connect(mock_connection):
    """
    Test subscribed to waiverdb after connected.
    """
    listener = waiverdb_listener()
    assert len(mock_connection.connect.mock_calls) == 1
    mock_connection.subscribe.assert_called_once_with(
        destination=WAIVERDB_QUEUE,
        id=listener.uid,
        ack="client-individual",
    )


def test_listener_unique_ids(mock_connection):
    """
    Test listeners have unique IDs.
    """
    listener1 = waiverdb_listener()
    listener2 = waiverdb_listener()
    assert listener1.uid != listener2.uid
    assert listener1.uid.startswith("greenwave-waiverdb-")
    assert listener2.uid.startswith("greenwave-waiverdb-")


def test_listener_reconnect(mock_retrieve_results, mock_connection):
    """
    Test reconnect on send failure.
    """
    listener = resultsdb_listener()

    assert len(mock_connection.connect.mock_calls) == 1
    assert len(mock_connection.send.mock_calls) == 0

    mock_connection.is_connected.side_effect = [False, True]
    mock_connection.send.side_effect = [stomp.exception.NotConnectedException, None]

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.connect.mock_calls) == 2
    assert len(mock_connection.send.mock_calls) == 2
    assert len(mock_connection.ack.mock_calls) == 1


def test_listener_send_failure(mock_connection):
    """
    Test exception on send.
    """
    listener = resultsdb_listener()

    mock_connection.send.side_effect = RuntimeError("FAILED")

    with pytest.raises(RuntimeError, match="FAILED"):
        listener.on_message(DummyMessage())

    assert len(mock_connection.send.mock_calls) == 1
    assert len(mock_connection.ack.mock_calls) == 1


def test_listener_nack_after_disconnect(mock_connection):
    """
    Test sending NACK after disconnect.
    """
    listener = resultsdb_listener()
    listener.disconnect()

    with listener.app.app_context():
        listener.on_message(DummyMessage())

    assert len(mock_connection.connect.mock_calls) == 1
    assert len(mock_connection.send.mock_calls) == 0
    assert len(mock_connection.nack.mock_calls) == 1


def test_listener_terminates_on_connect_failure(mock_connection):
    """
    Test terminating process after connection failure.
    """
    mock_connection.connect.side_effect = stomp.exception.ConnectFailedException
    with mock.patch("os.kill") as mock_kill:
        resultsdb_listener()
        assert len(mock_connection.disconnect.mock_calls) == 1
        assert len(mock_kill.mock_calls) == 1


def test_listener_terminates_on_disconnected(mock_connection):
    """
    Test terminating process on disconnect.
    """
    handler = resultsdb_listener()
    with mock.patch("os.kill") as mock_kill:
        handler.on_disconnected()
        assert len(mock_connection.disconnect.mock_calls) == 1
        assert len(mock_kill.mock_calls) == 1


def test_listener_terminates_on_receiver_loop_end(mock_connection):
    """
    Test terminating process on disconnect.
    """
    handler = resultsdb_listener()
    with mock.patch("os.kill") as mock_kill:
        handler.on_receiver_loop_completed(frame=mock.Mock())
        assert len(mock_connection.disconnect.mock_calls) == 1
        assert len(mock_kill.mock_calls) == 1


def test_listener_receive_non_json_message(mock_connection):
    """
    Test exception on send.
    """
    listener = resultsdb_listener()

    mock_connection.send.side_effect = RuntimeError("FAILED")

    class BadMessage(DummyMessage):
        @property
        def body(self):
            return "BAD"

    listener._inc = mock.Mock()

    listener.on_message(BadMessage())

    assert len(mock_connection.send.mock_calls) == 0
    assert len(mock_connection.ack.mock_calls) == 1

    listener._inc.assert_has_calls(
        [
            mock.call(messaging_rx_counter),
            mock.call(messaging_rx_ignored_counter),
        ]
    )
