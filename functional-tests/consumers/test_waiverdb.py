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
def test_consume_new_result(
        mock_fedmsg, load_config, greenwave_server, testdatabuilder, monkeypatch):
    monkeypatch.setenv('TEST', 'true')
    load_config.return_value = {'greenwave_api_url': greenwave_server.url + 'api/v1.0'}
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.abicheck',
                                           outcome='FAILED')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    testdatabuilder.create_waiver(result_id=result['id'], product_version='fedora-26')
    message = {
        'topic': 'waiver.new',
        "msg": {
            "comment": "Because I said so",
            "username": "foo",
            "waived": "true",
            "timestamp": "2017-08-10T17:42:04.209638",
            "product_version": "fedora-26",
            "result_id": result['id'],
        }
    }
    hub = mock.MagicMock()
    hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}
    handler = waiverdb.WaiverDBHandler(hub)
    assert handler.topic == ['topic_prefix.environment.waiver.new']
    handler.consume(message)
    msg = {
        'policies_satisified': True,
        'decision_context': 'bodhi_update_push_stable',
        'unsatisfied_requirements': [],
        'summary': 'all required tests passed',
        'product_version': 'fedora-26',
        'subject': [
            {
                'item': [nvr],
                'type': ['koji_build']
            }
        ],
        'applicable_policies': ['taskotron_release_critical_tasks']
    }
    mock_fedmsg.assert_called_once_with(
        topic='greenwave.decision.update', msg=msg)
