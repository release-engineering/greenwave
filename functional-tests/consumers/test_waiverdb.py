# SPDX-License-Identifier: GPL-2.0+

import mock

from greenwave.consumers import waiverdb


TASKTRON_RELEASE_CRITICAL_TASKS = [
    'dist.abicheck',
    'dist.rpmdeplint',
    'dist.upgradepath',
]


@mock.patch('greenwave.consumers.resultsdb.fedmsg.config.load_config')
@mock.patch('greenwave.consumers.waiverdb.fedmsg.publish')
def test_consume_new_waiver(
        mock_fedmsg, load_config, requests_session, greenwave_server, testdatabuilder):
    load_config.return_value = {'greenwave_api_url': greenwave_server + 'api/v1.0'}
    nvr = testdatabuilder.unique_nvr()
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    updateid = update['updateid']
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.abicheck',
                                           outcome='FAILED')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    testcase = str(result['testcase']['name'])
    waiver = testdatabuilder.create_waiver(nvr=nvr,
                                           testcase_name=testcase,
                                           product_version='fedora-26',
                                           comment='Because I said so')
    message = {
        'body': {
            'topic': 'waiver.new',
            "msg": waiver,
        }
    }
    hub = mock.MagicMock()
    hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}
    handler = waiverdb.WaiverDBHandler(hub)
    assert handler.topic == ['topic_prefix.environment.waiver.new']
    handler.consume(message)

    # We expect 2 messages altogether.
    assert len(mock_fedmsg.mock_calls) == 2
    assert all(call[2]['topic'] == 'decision.update' for call in mock_fedmsg.mock_calls)
    actual_msgs_sent = [call[2]['msg'] for call in mock_fedmsg.mock_calls]
    assert actual_msgs_sent[0] == {
        'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                'taskotron_release_critical_tasks'],
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_stable',
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                    'taskotron_release_critical_tasks'],
            'policies_satisfied': False,
            'summary': u'1 of 3 required tests failed',
            'unsatisfied_requirements': [
                {
                    'result_id': result['id'],
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'testcase': 'dist.abicheck',
                    'type': 'test-result-failed',
                    'scenario': None,
                },
            ],
        },
        'product_version': 'fedora-26',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
        ],
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'unsatisfied_requirements': [],
        'summary': 'all required tests passed',
        'testcase': testcase,
    }
    assert actual_msgs_sent[1] == {
        'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                'taskotron_release_critical_tasks'],
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_stable',
        'previous': {
            'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                    'taskotron_release_critical_tasks'],
            'policies_satisfied': False,
            'summary': u'1 of 3 required tests failed',
            'unsatisfied_requirements': [
                {
                    'result_id': result['id'],
                    'item': {'item': nvr, 'type': 'koji_build'},
                    'testcase': 'dist.abicheck',
                    'type': 'test-result-failed',
                    'scenario': None,
                },
            ],
        },
        'product_version': 'fedora-26',
        'subject': [
            {'item': updateid, 'type': 'bodhi_update'},
            {'item': nvr, 'type': 'koji_build'},
            {'original_spec_nvr': nvr},
        ],
        'subject_type': 'bodhi_update',
        'subject_identifier': updateid,
        'unsatisfied_requirements': [],
        'summary': 'all required tests passed',
        'testcase': testcase,
    }
