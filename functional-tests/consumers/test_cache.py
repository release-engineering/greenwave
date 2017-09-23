# SPDX-License-Identifier: GPL-2.0+

import json
import mock
import pprint

from greenwave.config import CachedTestingConfig
from greenwave.consumers import cache


def test_consume_new_result_with_mocked_cache(
        requests_session, cached_greenwave_server, testdatabuilder, monkeypatch):
    """ Consume a result, and ensure that `delete` is called. """
    monkeypatch.setenv('TEST', 'true')
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(
        item=nvr, testcase_name='dist.rpmdeplint', outcome='PASSED')
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
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
        'greenwave_cache': {'backend': 'dogpile.cache.memory'},
    }
    handler = cache.CacheInvalidatorExtraordinaire(hub)
    handler.cache = mock.MagicMock()
    assert handler.topic == [
        'topic_prefix.environment.taskotron.result.new',
        # Not ready to handle waiverdb yet.
        #'topic_prefix.environment.waiver.new',
    ]
    handler.consume(message)
    expected = ("greenwave.resources:retrieve_results|"
                "{'item': '%s', 'type': 'koji_build'}" % nvr)
    handler.cache.delete.assert_called_once_with(expected)


def test_consume_new_result_with_real_cache(
        requests_session, cached_greenwave_server, testdatabuilder, monkeypatch):
    monkeypatch.setenv('TEST', 'true')
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
    r = requests_session.post(cached_greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is passing...
    assert response['policies_satisified'], pprint.pformat(response)

    # Now, insert a new result and ensure that caching has made it such that
    # even though the new result fails, our decision still passes (bad)
    testdatabuilder.create_result(
        item=nvr, testcase_name='dist.abicheck', outcome='FAILED')
    r = requests_session.post(cached_greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is passing...  BUT IT SHOULDN'T BE!
    assert response['policies_satisified'], pprint.pformat(response)

    # Now, handle a message about the new failing result
    message = {
        u'topic': u'taskotron.result.new',
        u'msg': {
            u'result': {
                u'id': u'whatever',
                u'outcome': u'doesn\'t matter',
            },
            u'task': {
                u'item': nvr.decode('utf-8'),
                u'type': u'koji_build',
                u'name': u'dist.rpmdeplint'
            }
        }
    }
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
        'greenwave_cache': CachedTestingConfig().CACHE,
    }
    handler = cache.CacheInvalidatorExtraordinaire(hub)
    assert handler.topic == [
        'topic_prefix.environment.taskotron.result.new',
        # Not ready to handle waiverdb yet.
        #'topic_prefix.environment.waiver.new',
    ]
    handler.consume(message)

    # At this point, the invalidator should have invalidated the cache.  If we
    # ask again, the decision should be correct now.  It should be a stone cold
    # "no".
    r = requests_session.post(cached_greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(query))
    assert r.status_code == 200
    response = r.json()
    # Ensure it is failing -- as it should be.
    assert not response['policies_satisified'], pprint.pformat(response)
