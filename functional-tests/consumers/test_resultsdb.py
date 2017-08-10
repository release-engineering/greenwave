# SPDX-License-Identifier: GPL-2.0+

import mock

from greenwave.consumers import resultsdb


@mock.patch('greenwave.consumers.resultsdb.fedmsg.config.load_config')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_new_result(
        mock_fedmsg, load_config, greenwave_server, testdatabuilder, monkeypatch):
    monkeypatch.setenv('TEST', 'true')
    load_config.return_value = {'greenwave_api_url': greenwave_server.url + 'api/v1.0'}
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.rpmdeplint',
                                           outcome='PASSED')
    message = {
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
    hub = mock.MagicMock()
    hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}
    handler = resultsdb.ResultsDBHandler(hub)
    assert handler.topic == ['topic_prefix.environment.taskotron.result.new']
    handler.consume(message)
    msg = {
        'policies_satisified': False,
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'unsatisfied_requirements': [
            {
                'testcase': 'dist.abicheck',
                'item': {
                    'item': nvr,
                    'type': 'koji_build'
                },
                'type': 'test-result-missing'
            },
            {
                'testcase': 'dist.upgradepath',
                'item': {
                    'item': nvr,
                    'type': 'koji_build'
                },
                'type': 'test-result-missing'
            }
        ],
        'summary': '2 of 3 required tests not found',
        'subject': [
            {
                'item': nvr,
                'type': 'koji_build'
            }
        ],
        'applicable_policies': ['taskotron_release_critical_tasks']
    }
    mock_fedmsg.assert_called_once_with(
        topic='greenwave.decision.update', msg=msg)
