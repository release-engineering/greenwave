# SPDX-License-Identifier: GPL-2.0+

import hashlib
import mock
import time

from greenwave.consumers import resultsdb
from greenwave.utils import right_before_this_time

import handlers


def create_resultdb_handler(greenwave_server, cache_config=None):
    return handlers.create_handler(
        resultsdb.ResultsDBHandler,
        'topic_prefix.environment.taskotron.result.new',
        greenwave_server,
        cache_config)


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_consume_new_result(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder, koji_proxy):
    nvr = testdatabuilder.unique_nvr(product_version='fc26')
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.rpmdeplint',
                                           outcome='PASSED')
    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                },
                'submit_time': result['submit_time']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.consume(message)

    assert len(mock_fedora_messaging.mock_calls) == 2
    assert all(
        call[1][0].topic == "greenwave.decision.update"
        for call in mock_fedora_messaging.mock_calls
    )
    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[0] == {
        'policies_satisfied': False,
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'satisfied_requirements': [
            {
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'result_id': result['id'],
                'testcase': 'dist.rpmdeplint',
                'scenario': None,
                'system_architecture': None,
                'system_variant': None,
                'source': None,
                'type': 'test-result-passed',
            },
        ],
        'unsatisfied_requirements': [
            {
                'testcase': 'dist.abicheck',
                'item': {'item': nvr, 'type': 'koji_build'},
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'type': 'test-result-missing',
                'scenario': None,
                'source': None,
            },
            {
                'testcase': 'dist.upgradepath',
                'item': {'item': nvr, 'type': 'koji_build'},
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'type': 'test-result-missing',
                'scenario': None,
                'source': None,
            }
        ],
        'summary': 'Of 3 required tests, 2 results missing',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_with_blocklist',
                                'taskotron_release_critical_tasks'],
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_with_blocklist',
                                    'taskotron_release_critical_tasks'],
            'policies_satisfied': False,
            'summary': 'Of 3 required tests, 3 results missing',
            'satisfied_requirements': [],
            'unsatisfied_requirements': [
                {
                    'testcase': 'dist.abicheck',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                    'source': None,
                },
                {
                    'testcase': 'dist.rpmdeplint',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                    'source': None,
                },
                {
                    'testcase': 'dist.upgradepath',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                    'source': None,
                },
            ],
        },
    }
    assert actual_msgs_sent[1] == {
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_testing',
        'product_version': 'fedora-26',
        'satisfied_requirements': [
            {
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'result_id': result['id'],
                'testcase': 'dist.rpmdeplint',
                'scenario': None,
                'system_architecture': None,
                'system_variant': None,
                'type': 'test-result-passed',
                'source': None,
            },
        ],
        'unsatisfied_requirements': [],
        'summary': 'All required tests (1 total) have passed or been waived',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_for_testing'],
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_for_testing'],
            'policies_satisfied': False,
            'summary': 'Of 1 required test, 1 result missing',
            'satisfied_requirements': [],
            'unsatisfied_requirements': [
                {
                    'testcase': 'dist.rpmdeplint',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                    'source': None,
                },
            ],
        },
    }


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_consume_unchanged_result(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder):
    nvr = testdatabuilder.unique_nvr(product_version='fc26')

    testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')
    new_result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')

    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': new_result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                },
                'submit_time': new_result['submit_time']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.consume(message)

    assert len(mock_fedora_messaging.mock_calls) == 0


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_consume_compose_id_result(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder):
    compose_id = testdatabuilder.unique_compose_id()
    result = testdatabuilder.create_compose_result(
        compose_id=compose_id,
        testcase_name='compose.install_no_user',
        scenario='scenario1',
        outcome='PASSED')
    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'compose.install_no_user',
                },
                'data': {
                    'productmd.compose.id': [compose_id],
                },
                'submit_time': result['submit_time']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'rawhide_compose_sync_to_mirrors',
        'product_version': 'fedora-rawhide',
        'subject': [{'productmd.compose.id': compose_id}],
        'when': right_before_this_time(result['submit_time'])
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    old_decision = r.json()
    msg = {
        'applicable_policies': ['openqa_important_stuff_for_rawhide'],
        'decision_context': 'rawhide_compose_sync_to_mirrors',
        'policies_satisfied': False,
        'product_version': 'fedora-rawhide',
        'subject': [{'productmd.compose.id': compose_id}],
        'subject_type': 'compose',
        'subject_identifier': compose_id,
        'summary': 'Of 2 required tests, 1 result missing',
        'previous': old_decision,
        'satisfied_requirements': [{
            'subject_type': 'compose',
            'subject_identifier': compose_id,
            'result_id': result['id'],
            'scenario': 'scenario1',
            'system_architecture': None,
            'system_variant': None,
            'testcase': 'compose.install_no_user',
            'source': None,
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': [{
            'item': {'productmd.compose.id': compose_id},
            'subject_type': 'compose',
            'subject_identifier': compose_id,
            'scenario': 'scenario2',
            'source': None,
            'testcase': 'compose.install_no_user',
            'type': 'test-result-missing'}
        ]
    }

    assert len(mock_fedora_messaging.mock_calls) == 1
    assert all(
        call[1][0].topic == "greenwave.decision.update"
        for call in mock_fedora_messaging.mock_calls
    )
    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[0] == msg


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_consume_legacy_result(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder, koji_proxy):
    """ Test that we can still handle the old legacy "taskotron" format.

    We should be using resultsdb.result.new everywhere now, but we also
    need to be able to handle this taskotron format for the transition.
    """

    nvr = testdatabuilder.unique_nvr(product_version='fc26')
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.rpmdeplint',
                                           outcome='PASSED')
    message = {
        'body': {
            'topic': 'taskotron.result.new',
            'msg': {
                'result': {
                    'id': result['id'],
                    'outcome': 'PASSED'
                },
                'task': {
                    'item': nvr,
                    'type': 'koji_build',
                    'name': 'dist.rpmdeplint'
                },
                'submit_time': result['submit_time']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'when': right_before_this_time(result['submit_time']),
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    old_decision = r.json()
    # should have two messages published as we have two decision contexts applicable to
    # this subject.
    first_msg = {
        'policies_satisfied': False,
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'satisfied_requirements': [{
            'subject_type': 'koji_build',
            'subject_identifier': nvr,
            'result_id': result['id'],
            'scenario': None,
            'system_architecture': None,
            'system_variant': None,
            'testcase': 'dist.rpmdeplint',
            'source': None,
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': [
            {
                'testcase': 'dist.abicheck',
                'item': {
                    'item': nvr,
                    'type': 'koji_build'
                },
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'type': 'test-result-missing',
                'scenario': None,
                'source': None,
            },
            {
                'testcase': 'dist.upgradepath',
                'item': {
                    'item': nvr,
                    'type': 'koji_build'
                },
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'type': 'test-result-missing',
                'scenario': None,
                'source': None,
            }
        ],
        'summary': 'Of 3 required tests, 2 results missing',
        'subject': [
            {
                'item': nvr,
                'type': 'koji_build'
            }
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_with_blocklist',
                                'taskotron_release_critical_tasks'],
        'previous': old_decision,
    }

    assert all(
        call[1][0].topic == "greenwave.decision.update"
        for call in mock_fedora_messaging.mock_calls
    )
    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[0] == first_msg

    # get the old decision for the second policy
    data = {
        'decision_context': 'bodhi_update_push_testing',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'when': right_before_this_time(result['submit_time']),
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    old_decision = r.json()
    second_msg = {
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_testing',
        'product_version': 'fedora-26',
        'satisfied_requirements': [{
            'subject_type': 'koji_build',
            'subject_identifier': nvr,
            'result_id': result['id'],
            'scenario': None,
            'system_architecture': None,
            'system_variant': None,
            'testcase': 'dist.rpmdeplint',
            'source': None,
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': [],
        'summary': 'All required tests (1 total) have passed or been waived',
        'subject': [
            {
                'item': nvr,
                'type': 'koji_build'
            }
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_for_testing'],
        'previous': old_decision,
    }

    assert all(
        call[1][0].topic == "greenwave.decision.update"
        for call in mock_fedora_messaging.mock_calls
    )
    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[1] == second_msg


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_no_message_for_nonapplicable_policies(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    # One result gets the decision in a certain state.
    testdatabuilder.create_result(item=nvr,
                                  testcase_name='a_package_test',
                                  outcome='FAILED')
    # Recording a new version of the same result shouldn't change our decision at all.
    new_result = testdatabuilder.create_result(
        item=nvr,
        testcase_name='a_package_test',
        outcome='PASSED')
    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': new_result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'a_package_test',
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                },
                'submit_time': new_result['submit_time']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.consume(message)
    # No message should be published as the decision is unchanged since we
    # are still missing the required tests.
    mock_fedora_messaging.assert_not_called()


@mock.patch('greenwave.consumers.consumer.fedora_messaging.api.publish')
def test_consume_new_result_container_image(
        mock_fedora_messaging, requests_session, greenwave_server,
        testdatabuilder):
    unique_id = str(time.time()).encode('utf-8')
    sha256 = hashlib.sha256(unique_id).hexdigest()
    item_hash = 'fedora@sha256:{}'.format(sha256)
    result = testdatabuilder.create_result(item=item_hash,
                                           testcase_name='baseos-qe.baseos-ci.tier1.functional',
                                           outcome='PASSED', _type='container-image')
    message = {
        "body": {
            "username": None,
            "source_name": "datanommer",
            "certificate": None,
            "i": 0,
            "timestamp": 1546858448.0,
            "msg_id": "ID:umb-test-9999-umb-3-r7xk4-46608-1545211261969-3:248:-1:1:1",
            "crypto": None,
            "topic": "/topic/VirtualTopic.eng.resultsdb.result.new",
            "headers": {
                "content-length": "1441",
                "expires": "0",
                "timestamp": "1546858448379",
                "original-destination": "/topic/VirtualTopic.eng.resultsdb.result.new",
                "destination": "/queue/Consumer.client-datanommer.upshift-dev.VirtualTopic.eng.>",
                "priority": "4",
                "message-id": "ID:umb-test-9999-umb-3-r7xk4-46608-1545211261969-3:248:-1:1:1",
                "subscription": "/queue/Consumer.client-datanommer.upshift-dev.VirtualTopic.eng.>"
            },
            "signature": None,
            "source_version": "0.9.1",
            "msg": {
                "testcase": {
                    "ref_url": "https://example.com",
                    "href": ("http://resultsdb-test-9999-api-yuxzhu.cloud.paas.upshift.redhat."
                             "com/api/v2.0/testcases/baseos-qe.baseos-ci.tier1.functional"),
                    "name": "baseos-qe.baseos-ci.tier1.functional"
                },
                "ref_url": "https://somewhere.com/job/ci-openstack/4794",
                "note": "",
                "href": ("http://resultsdb-test-9999-api-yuxzhu.cloud.paas.upshift.redhat."
                         "com/api/v2.0/results/58"),
                "groups": [
                    "341d4cba-ffe2-4d83-b36c-5d819181e86d"
                ],
                "submit_time": result['submit_time'],
                "outcome": "PASSED",
                "data": {
                    "category": [
                        "functional"
                    ],
                    "log": [
                        "https://somewhere.com/job/ci-openstack/4794/console"
                    ],
                    "recipients": [
                        "mvadkert",
                        "ovasik"
                    ],
                    "ci_environment": [
                        "production"
                    ],
                    "scratch": [
                        "True"
                    ],
                    "rebuild": [
                        "https://somewhere.com/job/ci-openstack/4794/rebuild/parametrized"
                    ],
                    "ci_email": [
                        "pnt-devops-dev@example.com"
                    ],
                    "nvr": [
                        "fedora:28"
                    ],
                    "ci_name": [
                        "C3I Jenkins"
                    ],
                    "repository": [
                        "fedora"
                    ],
                    "item": [
                        item_hash
                    ],
                    "system_provider": [
                        "openstack"
                    ],
                    "ci_url": [
                        "https://example.com"
                    ],
                    "digest": [
                        "sha256:{}".format(sha256)
                    ],
                    "xunit": [
                        "https://somewhere.com/job/ci-openstack/4794/artifacts/results.xml"
                    ],
                    "system_architecture": [
                        "x86_64"
                    ],
                    "ci_team": [
                        "DevOps"
                    ],
                    "type": [
                        "container-image"
                    ],
                    "system_os": [
                        "rhel-7.4-server-x86_64-updated"
                    ],
                    "ci_irc": [
                        "#pnt-devops-dev"
                    ],
                    "issuer": [
                        "yuxzhu"
                    ]
                },
                "id": result['id']
            }
        }
    }
    handler = create_resultdb_handler(greenwave_server)
    handler.koji_base_url = None
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'container-image-test',
        'product_version': 'c3i',
        'subject': [{'item': item_hash, 'type': 'container-image'}],
        'when': right_before_this_time(result['submit_time']),
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    old_decision = r.json()

    actual_msgs_sent = [call[1][0].body for call in mock_fedora_messaging.mock_calls]
    assert actual_msgs_sent[0] == {
        'applicable_policies': ['container-image-policy'],
        'decision_context': 'container-image-test',
        'policies_satisfied': True,
        'product_version': 'c3i',
        'subject': [{'item': item_hash, 'type': 'container-image'}],
        'subject_type': 'container-image',
        'subject_identifier': item_hash,
        'summary': 'All required tests (1 total) have passed or been waived',
        'previous': old_decision,
        'satisfied_requirements': [{
            'subject_type': 'container-image',
            'subject_identifier': item_hash,
            'result_id': result['id'],
            'scenario': None,
            'system_architecture': None,
            'system_variant': None,
            'testcase': 'baseos-qe.baseos-ci.tier1.functional',
            'source': None,
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': []
    }
