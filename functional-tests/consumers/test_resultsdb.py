# SPDX-License-Identifier: GPL-2.0+

import json
import mock
import pprint

from greenwave.config import TestingConfig
from greenwave.consumers import resultsdb


def create_resultdb_handler(cache_config=None):
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }

    class Config(TestingConfig):
        CACHE = cache_config or TestingConfig.CACHE

    handler = resultsdb.ResultsDBHandler(hub, Config())
    assert handler.topic == [
        'topic_prefix.environment.taskotron.result.new',
        # Not ready to handle waiverdb yet.
        #'topic_prefix.environment.waiver.new',
    ]
    return handler


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_new_result(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder):
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
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 2
    assert all(call[2]['topic'] == 'decision.update' for call in mock_fedmsg.mock_calls)
    actual_msgs_sent = [call[2]['msg'] for call in mock_fedmsg.mock_calls]
    assert actual_msgs_sent[0] == {
        'policies_satisfied': False,
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'satisfied_requirements': [
            {
                'result_id': result['id'],
                'testcase': 'dist.rpmdeplint',
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
            },
            {
                'testcase': 'dist.upgradepath',
                'item': {'item': nvr, 'type': 'koji_build'},
                'subject_type': 'koji_build',
                'subject_identifier': nvr,
                'type': 'test-result-missing',
                'scenario': None,
            }
        ],
        'summary': '2 of 3 required test results missing',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                'taskotron_release_critical_tasks'],
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                    'taskotron_release_critical_tasks'],
            'policies_satisfied': False,
            'summary': '3 of 3 required test results missing',
            'satisfied_requirements': [],
            'unsatisfied_requirements': [
                {
                    'testcase': 'dist.abicheck',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                },
                {
                    'testcase': 'dist.rpmdeplint',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                },
                {
                    'testcase': 'dist.upgradepath',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
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
                'result_id': result['id'],
                'testcase': 'dist.rpmdeplint',
                'type': 'test-result-passed',
            },
        ],
        'unsatisfied_requirements': [],
        'summary': 'All required tests passed',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_for_testing'],
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_for_testing'],
            'policies_satisfied': False,
            'summary': '1 of 1 required test results missing',
            'satisfied_requirements': [],
            'unsatisfied_requirements': [
                {
                    'testcase': 'dist.rpmdeplint',
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'subject_type': 'koji_build',
                    'subject_identifier': nvr,
                    'type': 'test-result-missing',
                    'scenario': None,
                },
            ],
        },
    }


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_unchanged_result(
        mock_fedmsg, requests_session, greenwave_server,
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
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.consume(message)

    assert len(mock_fedmsg.mock_calls) == 0


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_invalidate_new_result_with_mocked_cache(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder):
    """ Consume a result, and ensure that `delete` is called. """
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')
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
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.cache = mock.MagicMock()
    handler.consume(message)
    cache_key1 = 'greenwave.resources:CachedResults|koji_build {} dist.rpmdeplint'.format(nvr)
    cache_key2 = 'greenwave.resources:CachedResults|koji_build {} None'.format(nvr)
    handler.cache.delete.assert_has_calls([
        mock.call(cache_key1),
        mock.call(cache_key2)
    ])
    assert handler.cache.delete.call_count == 2


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_invalidate_new_result_with_real_cache(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder, cache_config):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in ['dist.rpmdeplint', 'dist.upgradepath', 'dist.abicheck']:
        testdatabuilder.create_result(
            item=nvr, testcase_name=testcase_name, outcome='PASSED')

    # get first passing decision
    query = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is passing...
    assert response['policies_satisfied'], pprint.pformat(response)

    # Now, insert a new result and ensure that caching has made it such that
    # even though the new result fails, our decision still passes (bad)
    testdatabuilder.create_result(
        item=nvr, testcase_name='dist.abicheck', outcome='FAILED')
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is passing...  BUT IT SHOULDN'T BE!
    assert response['policies_satisfied'], pprint.pformat(response)

    # Now, handle a message about the new failing result
    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': 'whatever',
                'outcome': 'doesn\'t matter',
                'testcase': {
                    'name': 'dist.abicheck'
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    handler = create_resultdb_handler(cache_config)
    handler.consume(message)

    # At this point, the invalidator should have invalidated the cache.  If we
    # ask again, the decision should be correct now.  It should be a stone cold
    # "no".
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is failing -- as it should be.
    assert not response['policies_satisfied'], pprint.pformat(response)


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_invalidate_new_result_with_no_preexisting_cache(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder):
    """ Ensure that invalidating an unknown value is sane. """
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')
    message = {
        'body': {
            'topic': 'resultsdb.result.new',
            'msg': {
                'id': result['id'],
                'outcome': 'PASSED',
                'testcase': {
                    'name': 'dist.rpmdeplint'
                },
                'data': {
                    'item': [nvr],
                    'type': ['koji_build'],
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.cache.delete = mock.MagicMock()
    handler.consume(message)
    cache_key1 = 'greenwave.resources:CachedResults|koji_build {} dist.rpmdeplint'.format(nvr)
    cache_key2 = 'greenwave.resources:CachedResults|koji_build {} None'.format(nvr)
    handler.cache.delete.assert_has_calls([
        mock.call(cache_key1),
        mock.call(cache_key2)
    ])
    assert handler.cache.delete.call_count == 2


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_compose_id_result(
        mock_fedmsg, requests_session, greenwave_server,
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
            }
        }
    }
    handler = create_resultdb_handler()
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'rawhide_compose_sync_to_mirrors',
        'product_version': 'fedora-rawhide',
        'subject': [{'productmd.compose.id': compose_id}],
        'ignore_result': [result['id']]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
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
        'summary': '1 of 2 required test results missing',
        'previous': old_decision,
        'satisfied_requirements': [{
            'result_id': result['id'],
            'testcase': 'compose.install_no_user',
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': [{
            'item': {'productmd.compose.id': compose_id},
            'subject_type': 'compose',
            'subject_identifier': compose_id,
            'scenario': 'scenario2',
            'testcase': 'compose.install_no_user',
            'type': 'test-result-missing'}
        ]
    }

    mock_fedmsg.assert_called_once_with(topic='decision.update', msg=msg)


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_legacy_result(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder):
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
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'ignore_result': [result['id']]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    old_decision = r.json()
    # should have two messages published as we have two decision contexts applicable to
    # this subject.
    first_msg = {
        'policies_satisfied': False,
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'satisfied_requirements': [{
            'result_id': result['id'],
            'testcase': 'dist.rpmdeplint',
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
            }
        ],
        'summary': '2 of 3 required test results missing',
        'subject': [
            {
                'item': nvr,
                'type': 'koji_build'
            }
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                'taskotron_release_critical_tasks'],
        'previous': old_decision,
    }
    mock_fedmsg.assert_any_call(topic='decision.update', msg=first_msg)
    # get the old decision for the second policy
    data = {
        'decision_context': 'bodhi_update_push_testing',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'ignore_result': [result['id']]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    old_decision = r.json()
    second_msg = {
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_testing',
        'product_version': 'fedora-26',
        'satisfied_requirements': [{
            'result_id': result['id'],
            'testcase': 'dist.rpmdeplint',
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': [],
        'summary': 'All required tests passed',
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
    mock_fedmsg.assert_any_call(topic='decision.update', msg=second_msg)


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_no_message_for_nonapplicable_policies(
        mock_fedmsg, requests_session, greenwave_server,
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
                }
            }
        }
    }
    handler = create_resultdb_handler()
    handler.consume(message)
    # No message should be published as the decision is unchanged since we
    # are still missing the required tests.
    mock_fedmsg.assert_not_called()


@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_new_result_container_image(
        mock_fedmsg, requests_session, greenwave_server,
        testdatabuilder):
    nvr = 'fedora@sha256:017eb7de7927da933a04a6c1ff59da0c41dcea194aaa6b5dd7148df286b92433'
    result = testdatabuilder.create_result(item=nvr,
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
                "submit_time": "2019-01-07T10:54:08.265369",
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
                        ("fedora@sha256:017eb7de7927da933a04a6c1ff59da0c"
                         "41dcea194aaa6b5dd7148df286b92433")
                    ],
                    "system_provider": [
                        "openstack"
                    ],
                    "ci_url": [
                        "https://example.com"
                    ],
                    "digest": [
                        "sha256:017eb7de7927da933a04a6c1ff59da0c41dcea194aaa6b5dd7148df286b92433"
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
    handler = create_resultdb_handler()
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'container-image-test',
        'product_version': 'c3i',
        'subject': [{'item': nvr, 'type': 'container-image'}],
        'ignore_result': [result['id']]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    old_decision = r.json()

    msg = {
        'applicable_policies': ['container-image-policy'],
        'decision_context': 'container-image-test',
        'policies_satisfied': True,
        'product_version': 'c3i',
        'subject': [{'item': nvr, 'type': 'container-image'}],
        'subject_type': 'container-image',
        'subject_identifier': nvr,
        'summary': 'All required tests passed',
        'previous': old_decision,
        'satisfied_requirements': [{
            'result_id': result['id'],
            'testcase': 'baseos-qe.baseos-ci.tier1.functional',
            'type': 'test-result-passed'
        }],
        'unsatisfied_requirements': []
    }
    mock_fedmsg.assert_called_once_with(topic='decision.update', msg=msg)
