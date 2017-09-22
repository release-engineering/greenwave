# SPDX-License-Identifier: GPL-2.0+

import mock
import json

from greenwave.consumers import resultsdb


@mock.patch('greenwave.consumers.resultsdb.fedmsg.config.load_config')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_consume_new_result(
        mock_fedmsg, load_config, requests_session, greenwave_server, testdatabuilder, monkeypatch):
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

    # get old decision
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'ignore_result': [result['id']]
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    old_decision = r.json()

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
        'applicable_policies': ['taskotron_release_critical_tasks'],
        'previous': old_decision,
    }
    mock_fedmsg.assert_called_once_with(
        topic='greenwave.decision.update', msg=msg)


@mock.patch('greenwave.consumers.resultsdb.fedmsg.config.load_config')
@mock.patch('greenwave.consumers.resultsdb.fedmsg.publish')
def test_no_message_for_unchanged_decision(
        mock_fedmsg, load_config, requests_session, greenwave_server, testdatabuilder, monkeypatch):
    monkeypatch.setenv('TEST', 'true')
    load_config.return_value = {'greenwave_api_url': greenwave_server.url + 'api/v1.0'}
    nvr = testdatabuilder.unique_nvr()
    testdatabuilder.create_result(item=nvr,
                                  testcase_name='dist.rpmdeplint',
                                  outcome='PASSED')
    # create another new result for dist.rpmdeplint which passed again.
    new_result = testdatabuilder.create_result(
        item=nvr,
        testcase_name='dist.rpmdeplint',
        outcome='PASSED')
    message = {
        'topic': 'taskotron.result.new',
        'msg': {
            'result': {
                'id': new_result['id'],
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
    # No message should be published as the decision is unchanged since we
    # are still missing the required tests.
    mock_fedmsg.assert_not_called()
