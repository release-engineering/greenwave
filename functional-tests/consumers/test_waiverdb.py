# SPDX-License-Identifier: GPL-2.0+

from unittest import mock

import handlers
import pytest

from greenwave.consumers import waiverdb

TASKTRON_RELEASE_CRITICAL_TASKS = [
    "dist.abicheck",
    "dist.rpmdeplint",
    "dist.upgradepath",
]


def create_waiverdb_handler(greenwave_server):
    return handlers.create_handler(
        waiverdb.WaiverDBHandler,
        "topic_prefix.environment.waiver.new",
        greenwave_server,
    )


@pytest.mark.parametrize("subject_type", ("koji_build", "brew-build"))
@mock.patch("greenwave.consumers.consumer.fedora_messaging.api.publish")
def test_consume_new_waiver(
    mock_fedora_messaging,
    requests_session,
    greenwave_server,
    testdatabuilder,
    subject_type,
):
    nvr = testdatabuilder.unique_nvr()

    failing_test = TASKTRON_RELEASE_CRITICAL_TASKS[0]
    result = testdatabuilder.create_result(
        item=nvr, testcase_name=failing_test, outcome="FAILED", _type=subject_type
    )

    # The rest passed
    passing_tests = TASKTRON_RELEASE_CRITICAL_TASKS[1:]
    results = [
        testdatabuilder.create_result(
            item=nvr, testcase_name=testcase_name, outcome="PASSED", _type=subject_type
        )
        for testcase_name in passing_tests
    ]

    testcase = str(result["testcase"]["name"])
    waiver = testdatabuilder.create_waiver(
        nvr=nvr,
        testcase_name=testcase,
        product_version="fedora-26",
        comment="Because I said so",
        subject_type=subject_type,
    )
    message = {
        "body": {
            "topic": "waiver.new",
            "msg": waiver,
        }
    }
    handler = create_waiverdb_handler(greenwave_server)
    handler.consume(message)

    assert len(mock_fedora_messaging.mock_calls) == 1
    assert all(
        call[1][0].topic == "greenwave.decision.update"
        for call in mock_fedora_messaging.mock_calls
    )
    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[0] == {
        "applicable_policies": [
            "taskotron_release_critical_tasks_with_blocklist",
            "taskotron_release_critical_tasks",
        ],
        "policies_satisfied": True,
        "decision_context": "bodhi_update_push_stable",
        "previous": {
            "applicable_policies": [
                "taskotron_release_critical_tasks_with_blocklist",
                "taskotron_release_critical_tasks",
            ],
            "policies_satisfied": False,
            "summary": "Of 3 required tests, 1 test failed",
            "satisfied_requirements": [
                {
                    "subject_type": "koji_build",
                    "subject_identifier": nvr,
                    "result_id": results[0]["id"],
                    "scenario": None,
                    "system_architecture": None,
                    "system_variant": None,
                    "testcase": passing_tests[0],
                    "source": None,
                    "type": "test-result-passed",
                },
                {
                    "subject_type": "koji_build",
                    "subject_identifier": nvr,
                    "result_id": results[1]["id"],
                    "scenario": None,
                    "system_architecture": None,
                    "system_variant": None,
                    "testcase": passing_tests[1],
                    "source": None,
                    "type": "test-result-passed",
                },
            ],
            "unsatisfied_requirements": [
                {
                    "result_id": result["id"],
                    "item": {"item": nvr, "type": "koji_build"},
                    "subject_identifier": nvr,
                    "subject_type": "koji_build",
                    "testcase": failing_test,
                    "type": "test-result-failed",
                    "scenario": None,
                    "system_architecture": None,
                    "system_variant": None,
                    "source": None,
                },
            ],
        },
        "product_version": "fedora-26",
        "subject": [
            {"item": nvr, "type": "koji_build"},
        ],
        "subject_type": "koji_build",
        "subject_identifier": nvr,
        "satisfied_requirements": [
            {
                "subject_type": "koji_build",
                "subject_identifier": nvr,
                "result_id": result["id"],
                "waiver_id": waiver["id"],
                "testcase": failing_test,
                "type": "test-result-failed-waived",
                "scenario": None,
                "system_architecture": None,
                "system_variant": None,
                "source": None,
            },
            {
                "subject_type": "koji_build",
                "subject_identifier": nvr,
                "result_id": results[0]["id"],
                "scenario": None,
                "system_architecture": None,
                "system_variant": None,
                "testcase": passing_tests[0],
                "source": None,
                "type": "test-result-passed",
            },
            {
                "subject_type": "koji_build",
                "subject_identifier": nvr,
                "result_id": results[1]["id"],
                "scenario": None,
                "system_architecture": None,
                "system_variant": None,
                "testcase": passing_tests[1],
                "source": None,
                "type": "test-result-passed",
            },
        ],
        "unsatisfied_requirements": [],
        "summary": "All required tests (3 total) have passed or been waived",
        "testcase": testcase,
    }
