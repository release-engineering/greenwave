# SPDX-License-Identifier: GPL-2.0+

import json
import pytest

from textwrap import dedent

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


@pytest.mark.smoke
def test_any_policies_loaded(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/policies',
                             headers={'Content-Type': 'application/json'})
    assert r.status_code == 200
    body = r.json()
    policies = body['policies']
    assert len(policies) > 0


def test_inspect_policies(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/policies',
                             headers={'Content-Type': 'application/json'})
    assert r.status_code == 200
    body = r.json()
    policies = body['policies']
    assert len(policies) == 8
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


@pytest.mark.smoke
def test_version_endpoint(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/version')
    assert r.status_code == 200
    assert {'version': __version__} == r.json()


@pytest.mark.smoke
def test_about_endpoint_jsonp(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/about?callback=bac123')
    assert r.status_code == 200
    assert 'bac123' in r.text
    assert '"version": "%s"' % __version__ in r.text


@pytest.mark.smoke
def test_version_redirect(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/version')
    assert r.status_code == 200
    assert '"version": "%s"' % __version__ in r.text
    assert r.url.endswith('about')


@pytest.mark.smoke
def test_cannot_make_decision_without_product_version(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Missing required product version' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_decision_context(requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Missing required decision context' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_subject_type(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Missing required "subject_type" parameter' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_subject_identifier(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Missing required "subject_identifier" parameter' == r.json()['message']


@pytest.mark.smoke
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
    assert 'Invalid subject, must be a list of dicts' == r.json()['message']

    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': ['foo-1.0.0-1.el7'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert 'Invalid subject, must be a list of dicts' == r.json()['message']


@pytest.mark.smoke
def test_404_for_invalid_product_version(requests_session, greenwave_server, testdatabuilder):
    update = testdatabuilder.create_bodhi_update(build_nvrs=[testdatabuilder.unique_nvr()])
    data = {
        'decision_context': 'bodhi_push_update_stable',
        'product_version': 'f26',  # not a real product version
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 404
    expected = ('Cannot find any applicable policies for bodhi_update subjects '
                'at gating point bodhi_push_update_stable in f26')
    assert expected == r.json()['message']


@pytest.mark.smoke
def test_404_for_invalid_decision_context(requests_session, greenwave_server, testdatabuilder):
    update = testdatabuilder.create_bodhi_update(build_nvrs=[testdatabuilder.unique_nvr()])
    data = {
        'decision_context': 'bodhi_push_update',  # missing the _stable part!
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 404
    expected = ('Cannot find any applicable policies for bodhi_update subjects '
                'at gating point bodhi_push_update in fedora-26')
    assert expected == r.json()['message']


@pytest.mark.smoke
def test_415_for_missing_request_content_type(requests_session, greenwave_server):
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              data=json.dumps({}))
    assert r.status_code == 415
    expected = "No JSON payload in request"
    assert expected == r.json()['message']


@pytest.mark.smoke
def test_invalid_payload(requests_session, greenwave_server):
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data='not a json')
    assert r.status_code == 400
    message = r.json()['message']
    assert "Failed to decode JSON object" in message or \
        "sent a request that this server could not understand" in message


def test_make_a_decision_on_passed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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

    expected_satisfied_requirements = [
        {
            'result_id': result['id'],
            'testcase': result['testcase']['name'],
            'type': 'test-result-passed',
        } for result in results
    ]
    assert res_data['satisfied_requirements'] == expected_satisfied_requirements


def test_make_a_decision_with_verbose_flag_and_multiple_nvrs_with_results(
        requests_session, greenwave_server, testdatabuilder):
    build_nvrs = [testdatabuilder.unique_nvr(), testdatabuilder.unique_nvr()]

    results = []
    for nvr in reversed(build_nvrs):
        for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
            results.append(testdatabuilder.create_result(
                item=nvr, testcase_name=testcase_name, outcome='PASSED'))

    update = testdatabuilder.create_bodhi_update(build_nvrs=build_nvrs)
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == len(TASKTRON_RELEASE_CRITICAL_TASKS) * len(build_nvrs)
    assert res_data['results'] == list(reversed(results))


def test_make_a_decision_with_verbose_flag_and_multiple_nvrs_with_waivers(
        requests_session, greenwave_server, testdatabuilder):
    build_nvrs = [testdatabuilder.unique_nvr(), testdatabuilder.unique_nvr()]

    waivers = []
    for nvr in reversed(build_nvrs):
        for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
            waiver = testdatabuilder.create_waiver(
                nvr=nvr,
                product_version='fedora-26',
                testcase_name=testcase_name,
                comment='This is fine')
            waivers.append(waiver)

    update = testdatabuilder.create_bodhi_update(build_nvrs=build_nvrs)
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['waivers']) == len(TASKTRON_RELEASE_CRITICAL_TASKS) * len(build_nvrs)
    assert res_data['waivers'] == list(reversed(waivers))


def test_make_a_decision_on_failed_result_with_waiver(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    # First one failed but was waived
    testdatabuilder.create_result(item=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  outcome='FAILED')
    testdatabuilder.create_waiver(nvr=nvr,
                                  product_version='fedora-26',
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  comment='This is fine')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
            'subject_type': 'koji_build',
            'subject_identifier': nvr,
            'testcase': name,
            'type': 'test-result-missing',
            'scenario': None,
        } for name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_make_a_decision_on_no_results(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
            'subject_type': 'koji_build',
            'subject_identifier': nvr,
            'testcase': name,
            'type': 'test-result-missing',
            'scenario': None,
        } for name in TASKTRON_RELEASE_CRITICAL_TASKS
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_empty_policy_is_always_satisfied(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-24',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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


def test_bodhi_nonexistent_bodhi_update(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2000-deadbeaf',
    }
    r = requests_session.post(
        greenwave_server + 'api/v1.0/decision',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    assert res_data['summary'] == 'no tests are required'
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
            'subject_type': 'koji_build',
            'subject_identifier': nvr,
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
        'subject_type': 'compose',
        'subject_identifier': compose_id,
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
        'subject_type': 'compose',
        'subject_identifier': compose_id,
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
        'item': {'productmd.compose.id': compose_id},
        'result_id': result['id'],
        'testcase': testcase_name,
        'type': 'test-result-failed',
        'scenario': 'scenario2',
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
    waiver = testdatabuilder.create_waiver(nvr=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           product_version='fedora-26',
                                           comment='This is fine')
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
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
    update = testdatabuilder.create_bodhi_update(build_nvrs=[nvr])
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': update['updateid'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    # the failed test result of dist.abicheck should be ignored and thus the policy
    # is satisfied.
    assert res_data['policies_satisfied'] is True


def test_make_a_decision_about_brew_build(requests_session, greenwave_server, testdatabuilder):
    # The 'brew-build' type is used internally within Red Hat. We treat it as
    # the 'koji_build' subject type.
    nvr = testdatabuilder.unique_nvr(name='avahi')
    testdatabuilder.create_koji_build_result(
        nvr=nvr, testcase_name='osci.brew-build.tier0.functional',
        outcome='PASSED', type_='brew-build')
    data = {
        'decision_context': 'osci_compose_gate',
        'product_version': 'rhel-something',
        'subject': [{'type': 'brew-build', 'item': nvr}],
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == ['osci_compose']
    assert res_data['summary'] == 'all required tests passed'


def test_validate_gating_yaml_valid(requests_session, greenwave_server):
    gating_yaml = dedent("""
        --- !Policy
        id: "test"
        product_versions:
          - fedora-26
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test}
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == 'All OK'
    assert result.status_code == 200


def test_validate_gating_yaml_empty(requests_session, greenwave_server):
    result = requests_session.post(greenwave_server + 'api/v1.0/validate-gating-yaml')
    assert result.json().get('message') == 'No policies defined'
    assert result.status_code == 400


def test_validate_gating_yaml_missing_tag(requests_session, greenwave_server):
    gating_yaml = dedent("""
        ---
        id: "test"
        product_versions:
          - fedora-26
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test}
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == "Missing !Policy tag"
    assert result.status_code == 400


def test_make_a_decision_about_compose_all_variants_architectures(
        requests_session, greenwave_server, testdatabuilder):
    compose_id = testdatabuilder.unique_compose_id()

    failed_results = testdatabuilder.create_rtt_compose_result(
        compose_id=compose_id,
        variant='BaseOS',
        architecture='ppc64',
        outcome='FAILED')

    testdatabuilder.create_rtt_compose_result(
        compose_id=compose_id,
        variant='BaseOS',
        architecture='x86_64',
        outcome='PASSED')

    data = {
        'decision_context': 'rtt_compose_gate',
        'product_version': 'rhel-something',
        'subject_type': 'compose',
        'subject_identifier': compose_id,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert not res_data['policies_satisfied']
    assert res_data['unsatisfied_requirements'] == [{
        'item': {'productmd.compose.id': compose_id},
        'result_id': failed_results['id'],
        'scenario': None,
        'testcase': 'rtt.acceptance.validation',
        'type': 'test-result-failed'
    }]


def test_make_a_decision_about_compose_new_variants_architectures(
        requests_session, greenwave_server, testdatabuilder):
    compose_id = testdatabuilder.unique_compose_id()

    for arch, outcome in [('ppc64', 'FAILED'), ('ppc64', 'PASSED'), ('x86_64', 'PASSED')]:
        testdatabuilder.create_rtt_compose_result(
            compose_id=compose_id,
            variant='BaseOS',
            architecture=arch,
            outcome=outcome)

    data = {
        'decision_context': 'rtt_compose_gate',
        'product_version': 'rhel-something',
        'subject_type': 'compose',
        'subject_identifier': compose_id,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied']
