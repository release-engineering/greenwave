# SPDX-License-Identifier: GPL-2.0+

import mock
import json

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
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.abicheck',
                                           outcome='FAILED')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    testcase = str(result['testcase']['name'])
    waiver = testdatabuilder.create_waiver(result={
        "subject": dict([(str(key), str(value[0])) for key, value in result['data'].items()]),
        "testcase": testcase}, product_version='fedora-26', comment='Because I said so')
    message = {
        'body': {
            'topic': 'waiver.new',
            "msg": {
                "id": waiver['id'],
                "comment": "Because I said so",
                "username": "foo",
                "waived": "true",
                "timestamp": "2017-08-10T17:42:04.209638",
                "product_version": "fedora-26",
                "testcase": waiver['testcase'],
                "subject": [waiver['subject']]
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}
    handler = waiverdb.WaiverDBHandler(hub)
    assert handler.topic == ['topic_prefix.environment.waiver.new']
    handler.consume(message)

    # get old decision
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'ignore_waiver': [waiver['id']]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    old_decision = r.json()
    assert old_decision['summary'] == '1 of 3 required tests failed'

    msg = {
        'applicable_policies': ['taskotron_release_critical_tasks_with_blacklist',
                                'taskotron_release_critical_tasks'],
        'policies_satisfied': True,
        'decision_context': 'bodhi_update_push_stable',
        'previous': old_decision,
        'product_version': 'fedora-26',
        'subject': [
            {
                'item': nvr,
                'type': 'koji_build'
            }
        ],
        'unsatisfied_requirements': [],
        'summary': 'all required tests passed',
        'testcase': testcase,
    }
    mock_fedmsg.assert_called_once_with(
        topic='decision.update', msg=msg)
