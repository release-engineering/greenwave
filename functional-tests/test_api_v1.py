# SPDX-License-Identifier: GPL-2.0+

import pytest
import re
import os

from hashlib import sha256
from textwrap import dedent

from greenwave import __version__
from greenwave.utils import right_before_this_time


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
    assert len(policies) == 16
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
    expected = 'bac123({"version":"%s"});' % __version__
    actual = re.sub(r'\s+', '', r.text)
    assert expected == actual


@pytest.mark.smoke
def test_version_redirect(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/version')
    assert r.status_code == 200
    assert __version__, r.json()['version']
    assert r.url.endswith('about')


@pytest.mark.smoke
def test_cannot_make_decision_without_product_version(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Missing required product version' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_decision_context_and_user_policies(
        requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Either decision_context or rules is required.' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_subject_type(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Missing required "subject_type" parameter' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_subject_identifier(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Missing required "subject_identifier" parameter' == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_with_invalid_subject(requests_session, greenwave_server):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': 'foo-1.0.0-1.el7',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Invalid subject, must be a list of dicts' == r.json()['message']

    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': ['foo-1.0.0-1.el7'],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert 'Invalid subject, must be a list of dicts' == r.json()['message']


@pytest.mark.smoke
def test_404_for_invalid_product_version(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    data = {
        'decision_context': 'bodhi_push_update_stable',
        'product_version': 'f26',  # not a real product version
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 404
    expected = ('Cannot find any applicable policies for koji_build subjects '
                'at gating point bodhi_push_update_stable in f26')
    assert expected == r.json()['message']


@pytest.mark.smoke
def test_404_for_invalid_decision_context(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    data = {
        'decision_context': 'bodhi_push_update',  # missing the _stable part!
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 404
    expected = ('Cannot find any applicable policies for koji_build subjects '
                'at gating point bodhi_push_update in fedora-26')
    assert expected == r.json()['message']


@pytest.mark.smoke
def test_415_for_missing_request_content_type(requests_session, greenwave_server):
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json={})
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
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == [
        'taskotron_release_critical_tasks_with_blacklist',
        'taskotron_release_critical_tasks',
    ]
    expected_summary = 'All required tests passed'
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
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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

    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [
            {'type': 'koji_build', 'item': nvr}
            for nvr in build_nvrs
        ],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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

    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [
            {'type': 'koji_build', 'item': nvr}
            for nvr in build_nvrs
        ],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary


def test_make_a_decision_on_failed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='FAILED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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


def test_make_a_decision_on_queued_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='QUEUED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
            'subject_identifier': result['data']['item'][0],
            'subject_type': result['data']['type'][0],
            'testcase': TASKTRON_RELEASE_CRITICAL_TASKS[0],
            'scenario': None,
            'type': 'test-result-missing'
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


def test_make_a_decision_on_running_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           outcome='RUNNING')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
            'subject_identifier': result['data']['item'][0],
            'subject_type': result['data']['type'][0],
            'testcase': TASKTRON_RELEASE_CRITICAL_TASKS[0],
            'scenario': None,
            'type': 'test-result-missing'
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
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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


def test_subject_type_group(requests_session, greenwave_server, testdatabuilder):
    results_item = 'sha256:' + sha256(os.urandom(50)).hexdigest()

    testdatabuilder.create_result(
        item=results_item, testcase_name='testcase_name', outcome='PASSED', _type='group'
    )
    data = {
        'decision_context': 'compose_test_scenario_group',
        'product_version': 'fedora-30',
        'subject_type': 'group',
        'subject_identifier': results_item,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)

    assert r.status_code == 200

    res_data = r.json()
    assert res_data['satisfied_requirements'][0]['testcase'] == 'testcase_name'
    assert res_data['satisfied_requirements'][0]['type'] == 'test-result-passed'
    assert res_data['policies_satisfied'] is True

    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary


def test_empty_policy_is_always_satisfied(
        requests_session, greenwave_server, testdatabuilder):
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-24',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2000-abcdef01',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert 'taskotron_release_critical_tasks' in res_data['applicable_policies']
    assert 'taskotron_release_critical_tasks_with_blacklist' in res_data['applicable_policies']
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary
    assert res_data['unsatisfied_requirements'] == []


def test_bodhi_nonexistent_bodhi_update_policy(
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
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == []
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
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    result = testdatabuilder.create_result(
        item=nvr,
        testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
        outcome='PASSED')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    # Ignore one passing result
    data.update({
        'ignore_result': [result['id']]
    })
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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

    # repeating the test for "when" parameter instead of "ignore_result"
    # ...we should get the same behaviour.
    del(data['ignore_result'])
    data['when'] = right_before_this_time(result['submit_time'])
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == ['openqa_important_stuff_for_rawhide']
    expected_summary = 'All required tests passed'
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
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
    # The rest passed
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    waiver = testdatabuilder.create_waiver(nvr=nvr,
                                           testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                           product_version='fedora-26',
                                           comment='This is fine')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
    }
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r_.status_code == 200
    res_data = r_.json()
    assert res_data['policies_satisfied'] is True
    # Ignore the waiver
    data.update({
        'ignore_waiver': [waiver['id']]
    })
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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

    # repeating the test for "when" parameter instead of "ignore_waiver"
    # ...we should get the same behaviour.
    del(data['ignore_waiver'])
    data['when'] = right_before_this_time(waiver['timestamp'])
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r_.status_code == 200
    res_data = r_.json()
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
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2000-abcdef01',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True

    # Now, insert a *failing* result.  The cache should return the old results
    # that exclude the failing one (erroneously).
    testdatabuilder.create_result(item=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[-1],
                                  outcome='FAILED')
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2000-abcdef01',
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    # the failed test result of dist.abicheck should be ignored and thus the policy
    # is satisfied.
    assert res_data['policies_satisfied'] is True


def test_excluded_packages(requests_session, greenwave_server, testdatabuilder):
    """
    Test that packages in the excluded_packages list will be excluded when applying the policy.
    """
    nvr = testdatabuilder.unique_nvr(name='module-build-service')
    testdatabuilder.create_koji_build_result(
        nvr=nvr, testcase_name='osci.brew-build.tier0.functional',
        outcome='FAILED', type_='brew-build')
    data = {
        'decision_context': 'osci_compose_gate',
        'product_version': 'rhel-something',
        'subject': [{'type': 'brew-build', 'item': nvr}],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    # the failed test result of sci.brew-build.tier0.functiona should be ignored and thus the
    # policy is satisfied.
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

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    assert res_data['applicable_policies'] == ['osci_compose']
    assert res_data['summary'] == 'All required tests passed'


def test_validate_gating_yaml_valid(requests_session, greenwave_server):
    gating_yaml = dedent("""
        --- !Policy
        id: "test"
        product_versions:
          - fedora-26
        decision_context: container-image-test
        rules:
          - !PassingTestCaseRule {test_case_name: test}
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == 'All OK'
    assert result.status_code == 200


def test_validate_gating_yaml_deprecated_blacklist(requests_session, greenwave_server):
    gating_yaml = dedent("""
        --- !Policy
        id: "test"
        product_versions:
          - fedora-26
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test}
        blacklist:
          - python-requests
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == (
        'The gating.yaml file is valid but it is using the deprecated '
        '"blacklist" key. Please use "excluded_packages" instead.')
    assert result.status_code == 200


def test_validate_gating_yaml_empty(requests_session, greenwave_server):
    result = requests_session.post(greenwave_server + 'api/v1.0/validate-gating-yaml')
    assert result.json().get('message') == 'No policies defined'
    assert result.status_code == 400


def test_validate_gating_yaml_obsolete_rule(requests_session, greenwave_server):
    gating_yaml = dedent("""
        --- !Policy
        id: "test"
        product_versions:
          - fedora-26
        decision_context: test
        rules:
          - !PackageSpecificBuild {
              test_case_name: osci.brew-build.tier0.functional,
              repos: ["avahi", "cockpit"]
            }
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == (
        'Policy \'test\': Attribute \'rules\': !PackageSpecificBuild is obsolete. '
        'Please use the "packages" whitelist instead.')
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


def test_validate_gating_yaml_missing_decision_context(requests_session, greenwave_server):
    gating_yaml = dedent("""
        --- !Policy
        id: "test"
        product_versions:
          - fedora-26
        decision_context: test_missing_1
        rules:
          - !PassingTestCaseRule {test_case_name: test}

        --- !Policy
        id: "test_2"
        product_versions:
          - fedora-26
        decision_context: test_missing_2
        rules:
          - !PassingTestCaseRule {test_case_name: test_2}
    """)
    result = requests_session.post(
        greenwave_server + 'api/v1.0/validate-gating-yaml', data=gating_yaml)
    assert result.json().get('message') == ('Greenwave could not find a parent policy(ies) for '
                                            'following decision context(s): '
                                            'test_missing_1, test_missing_2. Please change your'
                                            ' policy so that it will match a decision'
                                            ' context in the parent policies.')
    assert result.status_code == 200


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
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
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
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied']


def test_make_a_decision_for_bodhi_with_verbose_flag(
        requests_session, greenwave_server, testdatabuilder):
    """
    Bodhi uses verbose flag to get all results.
    """
    nvrs = [
        testdatabuilder.unique_nvr(),
        testdatabuilder.unique_nvr(),
    ]

    results = []
    for nvr in reversed(nvrs):
        for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
            results.append(testdatabuilder.create_result(
                item=nvr, testcase_name=testcase_name, outcome='PASSED'))

    data = {
        'decision_context': 'bodhi_update_push_stable_with_no_rules',
        'product_version': 'fedora-28',
        'subject': [
            {'type': 'koji_build', 'item': nvr}
            for nvr in nvrs
        ] + [
            {'type': 'bodhi_update', 'item': 'FEDORA-2000-abcdef01'}
        ],
        'verbose': True,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == len(TASKTRON_RELEASE_CRITICAL_TASKS) * len(nvrs)
    assert res_data['results'] == list(reversed(results))
    assert res_data['waivers'] == []
    assert res_data['satisfied_requirements'] == []


def test_decision_on_redhat_module(requests_session, greenwave_server, testdatabuilder):
    nvr = '389-ds-1.4-820181127205924.9edba152'
    new_result_data = {
        'testcase': {'name': 'baseos-ci.redhat-module.tier0.functional'},
        'outcome': 'PASSED',
        'data': {'item': nvr, 'type': 'redhat-module'}
    }
    result = testdatabuilder._create_result(new_result_data) # noqa
    data = {
        'decision_context': 'osci_compose_gate_modules',
        'product_version': 'rhel-8',
        'subject_type': 'redhat-module',
        'subject_identifier': nvr,
        'verbose': True
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary
    assert res_data['results'][0]['data']['type'][0] == 'redhat-module'


def test_verbose_retrieve_latest_results(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for outcome in ['FAILED', 'PASSED']:
        for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS:
            testdatabuilder.create_result(item=nvr,
                                          testcase_name=testcase_name,
                                          outcome=outcome)
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'verbose': True
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary
    assert len(res_data['results']) == 3
    for result in res_data['results']:
        assert result['outcome'] == 'PASSED'


def test_make_decision_passed_on_subject_type_bodhi_with_waiver(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    # First one failed but was waived
    testdatabuilder.create_result(item=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  outcome='FAILED',
                                  _type='bodhi_update')
    testdatabuilder.create_waiver(nvr=nvr,
                                  product_version='fedora-26',
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  comment='This is fine',
                                  subject_type='bodhi_update')

    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED',
                                      _type='bodhi_update')

    data = {
        'decision_context': 'bodhi_update_push',
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': nvr,
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True

    assert res_data['applicable_policies'] == [
        'bodhi-test-policy',
    ]
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary


def test_make_a_decision_with_verbose_flag_all_results_returned(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    expected_waivers = []
    # First one failed but was waived
    results.append(testdatabuilder.create_result(item=nvr,
                                                 testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                                 outcome='FAILED'))
    expected_waivers.append(
        testdatabuilder.create_waiver(nvr=nvr,
                                      product_version='fedora-30',
                                      testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                      comment='This is fine'))
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        results.append(testdatabuilder.create_result(item=nvr,
                                                     testcase_name=testcase_name,
                                                     outcome='PASSED'))

    data = {
        'decision_context': 'koji_build_push_missing_results',
        'product_version': 'fedora-30',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'verbose': True,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == len(results)
    assert res_data['results'] == list(reversed(results))
    assert len(res_data['waivers']) == len(expected_waivers)
    assert res_data['waivers'] == expected_waivers


def test_verbose_retrieve_latest_results_scenario(requests_session, greenwave_server,
                                                  testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    for scenario in ['fedora.universal.x86_64.uefi', 'fedora.universal.x86_64.64bit']:
        results.append(testdatabuilder.create_compose_result(compose_id=nvr,
                       testcase_name='testcase_name', outcome='PASSED', scenario=scenario))
    data = {
        'decision_context': 'compose_test_scenario',
        'product_version': 'fedora-29',
        'subject_type': 'compose',
        'subject_identifier': nvr,
        'verbose': True
    }

    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisfied'] is True
    expected_summary = 'All required tests passed'
    assert res_data['summary'] == expected_summary
    assert len(res_data['results']) == 2
    for result in res_data['results']:
        assert result['outcome'] == 'PASSED'


def test_api_returns_not_repeated_waiver_in_verbose_info(
        requests_session, greenwave_server, testdatabuilder):
    """
    This tests that the API doesn't return repeated waivers when the flag verbose==True
    """
    nvr = testdatabuilder.unique_nvr()
    testdatabuilder.create_waiver(nvr=nvr,
                                  testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                  product_version='fedora-26',
                                  comment='This is fine')
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject': [
            {'item': nvr, 'type': 'koji_build'},
            {'original_spec_nvr': nvr},
        ],
        'verbose': True
    }
    r_ = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r_.status_code == 200
    res_data = r_.json()
    assert len(res_data['waivers']) == 1


def test_api_with_when(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    results.append(testdatabuilder.create_result(item=nvr,
                                                 testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[1],
                                                 outcome='PASSED'))
    results.append(testdatabuilder.create_result(item=nvr,
                                                 testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[2],
                                                 outcome='FAILED'))
    data = {
        'decision_context': 'bodhi_update_push_stable',
        'product_version': 'fedora-26',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'when': right_before_this_time(results[1]['submit_time']),
        'verbose': True,
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == 1
    assert res_data['results'] == [results[0]]

    del data['when']
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == 2


@pytest.mark.smoke
def test_cannot_make_decision_with_both_decision_context_and_user_policies(
        requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
        'decision_context': 'koji_build_push_missing_results',
        'rules': [
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'osci.brew-build.rpmdeplint.functional'
            },
        ],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert ('Cannot have both decision_context and rules') == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_required_rule_type(
        requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
        'rules': [
            {
                'typo': 'PassingTestCaseRule',
                'test_case_name': 'dist.abicheck'
            },
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.rpmdeplint'
            },
        ],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert ('Key \'type\' is required for every rule') == r.json()['message']


@pytest.mark.smoke
def test_cannot_make_decision_without_required_rule_testcase_name(
        requests_session, greenwave_server):
    data = {
        'product_version': 'fedora-26',
        'subject_type': 'bodhi_update',
        'subject_identifier': 'FEDORA-2018-ec7cb4d5eb',
        'rules': [
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.abicheck'
            },
            {
                'type': 'PassingTestCaseRule'
            },
        ],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 400
    assert ('Key \'test_case_name\' is required if not a RemoteRule') == r.json()['message']


def test_make_a_decision_with_verbose_flag_on_demand_policy(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    expected_waivers = []
    # First one failed but was waived
    results.append(testdatabuilder.create_result(item=nvr,
                                                 testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                                 outcome='FAILED'))
    expected_waivers.append(
        testdatabuilder.create_waiver(nvr=nvr,
                                      product_version='fedora-31',
                                      testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                      comment='This is fine'))
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        results.append(testdatabuilder.create_result(item=nvr,
                                                     testcase_name=testcase_name,
                                                     outcome='PASSED'))

    data = {
        'product_version': 'fedora-31',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'verbose': True,
        'rules': [
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.abicheck'
            },
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.rpmdeplint'
            },
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.upgradepath'
            },
        ],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['results']) == len(results)
    assert res_data['results'] == list(reversed(results))
    assert len(res_data['waivers']) == len(expected_waivers)
    assert res_data['waivers'] == expected_waivers
    assert len(res_data['satisfied_requirements']) == len(results)
    assert len(res_data['unsatisfied_requirements']) == 0


def test_make_a_decision_on_demand_policy(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    results = []
    expected_waivers = []
    # First one failed but was waived
    results.append(testdatabuilder.create_result(item=nvr,
                                                 testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                                 outcome='FAILED'))
    expected_waivers.append(
        testdatabuilder.create_waiver(nvr=nvr,
                                      product_version='fedora-31',
                                      testcase_name=TASKTRON_RELEASE_CRITICAL_TASKS[0],
                                      comment='This is fine'))
    for testcase_name in TASKTRON_RELEASE_CRITICAL_TASKS[1:]:
        results.append(testdatabuilder.create_result(item=nvr,
                                                     testcase_name=testcase_name,
                                                     outcome='PASSED'))

    data = {
        'id': 'on_demand',
        'product_version': 'fedora-31',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'rules': [
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.abicheck'
            },
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.rpmdeplint'
            },
            {
                'type': 'PassingTestCaseRule',
                'test_case_name': 'dist.upgradepath'
            },
        ],
    }
    r = requests_session.post(greenwave_server + 'api/v1.0/decision', json=data)
    assert r.status_code == 200
    res_data = r.json()

    assert len(res_data['satisfied_requirements']) == len(results)
    assert len(res_data['unsatisfied_requirements']) == 0


@pytest.mark.smoke
def test_installed_subject_types(requests_session, greenwave_server):
    response = requests_session.get(greenwave_server + 'api/v1.0/subject_types')
    assert response.status_code == 200
    data = response.json()
    assert len(data['subject_types'])
    assert [x['id'] for x in data['subject_types']] == [
        'bodhi_update',
        'compose',
        'koji_build',
        'redhat-container-image',
        'redhat-module',
    ]
