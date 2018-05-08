# SPDX-License-Identifier: GPL-2.0+

import json

from greenwave import __version__


TASKTRON_RELEASE_CRITICAL_TASKS = [
    'dist.abicheck',
    'dist.rpmdeplint',
    'dist.upgradepath',
]

OPENQA_SCENARIOS = [
    'scenario1',
    'scenario2',
]


def test_inspect_policies(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/policies',
                             headers={'Content-Type': 'application/json'})
    assert r.status_code == 200
    body = r.json()
    policies = body['policies']
    assert len(policies) == 6
    assert any(p['id'] == 'taskotron_release_critical_tasks' for p in policies)
    assert any(p['decision_context'] == 'bodhi_update_push_stable' for p in policies)
    assert any(p['product_versions'] == ['fedora-26'] for p in policies)
    expected_rules = [
        {'rule': 'PassingTestCaseRule',
         'test_case_name': 'dist.abicheck',
         'scenario': None},
    ]
    assert any(p['rules'] == expected_rules for p in policies)
    expected_rules = [
        {'rule': 'PassingTestCaseRule',
         'test_case_name': 'dist.rpmdeplint',
         'scenario': None},
        {'rule': 'PassingTestCaseRule',
         'test_case_name': 'dist.upgradepath',
         'scenario': None}]
    assert any(p['rules'] == expected_rules for p in policies)


def test_version_endpoint(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/version')
    assert r.status_code == 200
    assert {'version': __version__} == r.json()


def test_version_endpoint_jsonp(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/version?callback=bac123')
    assert r.status_code == 200
    assert 'bac123' in r.text
    assert '"version": "%s"' % __version__ in r.text


def test_cannot_make_decision_without_product_version(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'subject': [{'item': 'foo-1.0.0-1.el7', 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required product version' == r.json()['message']


def test_cannot_make_decision_without_decision_context(requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject': [{'item': 'foo-1.0.0-1.el7', 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required decision context' == r.json()['message']


def test_cannot_make_decision_without_subject(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required subject' == r.json()['message']


def test_cannot_make_decision_with_invalid_subject(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': 'foo-1.0.0-1.el7',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Invalid subject, must be a list of items' == r.json()['message']

    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': ['foo-1.0.0-1.el7'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Invalid subject, must be a list of dicts' in r.text


def test_404_for_invalid_product_version(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_push_update_stable',
        'product_version': 'f26',  # not a real product version
        'subject': [{'item': 'foo-1.0.0-1.el7', 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 404
    expected = u'Cannot find any applicable policies for f26 and bodhi_push_update_stable'
    assert expected == r.json()['message']


def test_404_for_invalid_decision_context(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_push_update',  # missing the _stable part!
        'product_version': 'fedora-26',
        'subject': [{'item': 'foo-1.0.0-1.el7', 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 404
    expected = u'Cannot find any applicable policies for fedora-26 and bodhi_push_update'
    assert expected == r.json()['message']


def test_415_for_missing_request_content_type(requests_session, greenwave_server):
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              data=json.dumps({}))
    assert r.status_code == 415
    expected = "No JSON payload in request"
    assert expected == r.json()['message']


def test_invalid_payload(requests_session, greenwave_server):
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data='not a json')
    assert r.status_code == 400
    expected = "Failed to decode JSON object: Expecting value: line 1 column 1 (char 0)"
    assert expected == r.json()['message']


def test_make_a_decision_on_passed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == [
        'taskotron_release_critical_tasks_with_blacklist',
        'taskotron_release_critical_tasks',
    ]
    expected_summary = 'all required tests passed'
    assert res_data['summary'] == expected_summary


def test_make_a_decision_with_verbose_flag(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        results.append(testdatabuilder.create_result(item=nvr,
                                                     testcase_name=testcase_name,
                                                     outcome='PASSED'))
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == len(TASKTRON_RELEASE_CRITICAL_TASKS)
    assert res_data['results'] == list(reversed(results))
    expected_waivers = []
    assert res_data['waivers'] == expected_waivers


def test_make_a_decision_on_failed_result_with_waiver(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    # First one failed but was waived
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='FAILED')
    waiver = testdatabuilder.create_waiver(result={ # noqa
        "subject": dict([(key, value[0]) for key, value in result['data'].items()]),
        "testcase": TASKTRON_RELEASE_CRITICAL_TASKS[0]}, product_version='fedora-26',
        comment='This is fine')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = 'all required tests passed'
    assert res_data['summary'] == expected_summary


def test_make_a_decision_on_failed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='FAILED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is False
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = '1 of 3 required tests failed, 2 results missing'
    assert res_data['summary'] == expected_summary
    expected_unsatisfied_requirements = [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'result_id': result['id'],
            'testcase': TASKTRON_RELEASE_CRITICAL_TASKS[0],
            'scenario': None,
            'type': 'test-result-failed'
        },
    ] + [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'testcase': name,
            'type': 'test-result-missing',
            'scenario': None,
        } for name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]
    ]
    assert sorted(res_data['unsatisfied_requirements']) == sorted(expected_unsatisfied_requirements)


def test_make_a_decision_on_no_results(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is False
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = '3 of 3 required test results missing'
    assert res_data['summary'] == expected_summary
    expected_unsatisfied_requirements = [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'testcase': name,
            'type': 'test-result-missing',
            'scenario': None,
        } for name in TASKTRON_RELEASE_CRITICAL_TASKS
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_empty_policy_is_always_satisfied(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-24',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == ['empty-policy']
    expected_summary = 'no tests are required'
    assert res_data['summary'] == expected_summary
    assert res_data['unsatisfied_requirements'] == []


def test_bodhi_push_update_stable_policy(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = 'all required tests passed'
    assert res_data['summary'] == expected_summary
    assert res_data['unsatisfied_requirements'] == []


def test_multiple_results_in_a_subject(
        requests_session, greenwave_server, testdatabuilder):
    """
    This makes sure that Greenwave uses the latest test result when a subject has
    multiple test restuls.
    """
    nvr = testdatabuilder.unique_nvr()
    testdatabuilder.create_result(item=nvr,
                                  testcase_name='dist.abicheck',
                                  outcome='PASSED')
    # create one failed test result for dist.abicheck
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.abicheck',
                                           outcome='FAILED')
    # the rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    # The failed result should be taken into account.
    assert res_data['policies_satisfied'] is False
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    assert res_data['summary'] == '1 of 3 required tests failed'
    expected_unsatisfied_requirements = [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'result_id': result['id'],
            'testcase': 'dist.abicheck',
            'type': 'test-result-failed',
            'scenario': None,
        },
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_ignore_result(requests_session, greenwave_server, testdatabuilder):
    """
    This tests that a result can be ignored when making the decision.
    """
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(
        item=nvr,
        testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
        outcome='PASSED')
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    # Ignore one passing result
    data.update({
        'ignore_result': [result['id']]
    })
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    expected_unsatisfied_requirements = [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'testcase': TASKTRON_RELEASE_CRITICAL_TASKS[0],
            'type': 'test-result-missing',
            'scenario': None,
        },
    ]
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is False
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_make_a_decision_on_passed_result_with_scenario(
        requests_session, greenwave_server, testdatabuilder):
    """
    If we require two scenarios to pass, and both pass, then we pass.
    """
    compose_id = testdatabuilder.unique_compose_id()
    testcase_name = 'compose.install_no_user'
    for scenario in OPENQA_SCENARIOS:
        testdatabuilder.create_compose_result(
            compose_id=compose_id,
            testcase_name=testcase_name,
            scenario=scenario,
            outcome='PASSED')
    data = {
        'decision_context': 'rawhide_compose_sync_to_mirrors',
        'product_version': 'fedora-rawhide',
        'subject': [{'productmd.compose.id': compose_id}],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == ['openqa_important_stuff_for_rawhide']
    expected_summary = 'all required tests passed'
    assert res_data['summary'] == expected_summary


def test_make_a_decision_on_failing_result_with_scenario(
        requests_session, greenwave_server, testdatabuilder):
    """
    If we require two scenarios to pass, and one is failing, then we fail.
    """

    compose_id = testdatabuilder.unique_compose_id()
    testcase_name = 'compose.install_no_user'
    # Scenario 1 passes..
    testdatabuilder.create_compose_result(
        compose_id=compose_id,
        testcase_name=testcase_name,
        scenario='scenario1',
        outcome='PASSED')
    # But scenario 2 fails!
    result = testdatabuilder.create_compose_result(
        compose_id=compose_id,
        testcase_name=testcase_name,
        scenario='scenario2',
        outcome='FAILED')
    data = {
        'decision_context': 'rawhide_compose_sync_to_mirrors',
        'product_version': 'fedora-rawhide',
        'subject': [{'productmd.compose.id': compose_id}],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is False
    assert res_data['applicable_policies'] == ['openqa_important_stuff_for_rawhide']
    expected_summary = '1 of 2 required tests failed'
    assert res_data['summary'] == expected_summary
    expected_unsatisfied_requirements = [{
        u'item': {u'productmd.compose.id': compose_id},
        u'result_id': result['id'],
        u'testcase': testcase_name,
        u'type': u'test-result-failed',
        u'scenario': u'scenario2',
    }]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_ignore_waiver(requests_session, greenwave_server, testdatabuilder):
    """
    This tests that a waiver can be ignored when making the decision.
    """
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='FAILED')
    waiver = testdatabuilder.create_waiver(result={
        "subject": dict([(key, value[0]) for key, value in result['data'].items()]),
        "testcase": TASKTRON_RELEASE_CRITICAL_TASKS[0]}, product_version='fedora-26',
        comment='This is fine')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision',
                               headers={'Content-Type': 'application/json'},
                               data=json.dumps(data))
    assert r_.status_code == 200
    res_data = r_.json()
    assert res_data['policies_satisfied'] is True
    # Ignore the waiver
    data.update({
        'ignore_waiver': [waiver['id']]
    })
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision',
                               headers={'Content-Type': 'application/json'},
                               data=json.dumps(data))
    assert r_.status_code == 200
    res_data = r_.json()
    expected_unsatisfied_requirements = [
        {
            'item': {'item': nvr, 'type': 'koji_build'},
            'result_id': result['id'],
            'testcase': TASKTRON_RELEASE_CRITICAL_TASKS[0],
            'type': 'test-result-failed',
            'scenario': None,
        },
    ]
    assert res_data['policies_satisfied'] is False
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_distgit_server(requests_session, distgit_server, tmpdir):
    """ This test is checking if the distgit server is working.
        Check that the file is present and that the server is running.
    """
    r_ = requests_session.head(distgit_server, headers={'Content-Type': 'application/json'},
                               timeout=60)
    assert r_.status_code == 200


def test_cached_false_positive(requests_session, greenwave_server, testdatabuilder):
    """ Test that caching without invalidation produces false positives.

    This just tests that our caching works in the first place.
    - Check a decision, it passes.
    - Insert a failing result.
    - Check the decision again, it passes

    (but it shouldn't) which means caching works.
    """
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True

    # Now, insert a *failing* result.  The cache should return the old results
    # that exclude the failing one (erroneously).
    testdatabuilder.create_result(item=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[-1],
                                  outcome='FAILED')
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True


def test_blacklist(requests_session, greenwave_server, testdatabuilder):
    """
    Test that packages on the blacklist will be excluded when applying the policy.
    """
    nvr = 'firefox-1.0-1.el7'
    testdatabuilder.create_result(item=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  outcome='FAILED')
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [{'item': nvr, 'type': 'koji_build'}]
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    # the failed test result of dist.abicheck should be ignored and thus the policy
    # is satisfied.
    assert res_data['policies_satisfied'] is True
