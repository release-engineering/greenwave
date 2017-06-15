# SPDX-License-Identifier: GPL-2.0+

import json


all_rpmdiff_testcase_names = [
    # XXX this is not all of them
    'dist.rpmdiff.comparison.xml_validity',
    'dist.rpmdiff.comparison.virus_scan',
    'dist.rpmdiff.comparison.upstream_source',
    'dist.rpmdiff.comparison.symlinks',
    'dist.rpmdiff.comparison.binary_stripping',
]


def test_cannot_make_decision_without_product_version(requests_session, greenwave_server):
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required product version' in r.text


def test_cannot_make_decision_without_decision_context(requests_session, greenwave_server):
    data = {
        'product_version': 'rhel-7',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required decision context' in r.text


def test_cannot_make_decision_without_subject(requests_session, greenwave_server):
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'product_version': 'rhel-7',
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 400
    assert u'Missing required subject' in r.text


def test_404_for_inapplicable_policies(requests_session, greenwave_server):
    data = {
        'decision_context': 'dummpy_decision',
        'product_version': 'rhel-7',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 404
    assert u'Cannot find any applicable policies for rhel-7' in r.text


def test_make_a_decison_on_passed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    for testcase_name in all_rpmdiff_testcase_names:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'product_version': 'rhel-7',
        'subject': [nvr]
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisified'] is True
    assert res_data['applicable_policies'] == ['1']
    expected_summary = '{}: policy 1 is satisfied as all required tests are passing'.format(nvr)
    assert res_data['summary'] == expected_summary


def test_make_a_decison_on_failed_result_with_waiver(
        requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    # First one failed but was waived
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name=all_rpmdiff_testcase_names[0],
                                           outcome='FAILED')
    testdatabuilder.create_waiver(result_id=result['id'], product_version='rhel-7')
    # The rest passed
    for testcase_name in all_rpmdiff_testcase_names[1:]:
        testdatabuilder.create_result(item=nvr,
                                      testcase_name=testcase_name,
                                      outcome='PASSED')
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'product_version': 'rhel-7',
        'subject': [nvr]
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisified'] is True
    assert res_data['applicable_policies'] == ['1']
    expected_summary = '{}: policy 1 is satisfied as all required tests are passing'.format(nvr)
    assert res_data['summary'] == expected_summary


def test_make_a_decison_on_failed_result(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    result = testdatabuilder.create_result(item=nvr,
                                           testcase_name='dist.rpmdiff.comparison.xml_validity',
                                           outcome='FAILED')
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'product_version': 'rhel-7',
        'subject': [nvr]
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisified'] is False
    assert res_data['applicable_policies'] == ['1']
    # XXX actually 1 failed and 4 are missing, need to improve this summary
    expected_summary = '{}: 5 of 5 required tests failed, the policy 1 is not satisfied'.format(nvr)
    assert res_data['summary'] == expected_summary
    expected_unsatisfied_requirements = [
        {
            'item': nvr,
            'result_id': result['id'],
            'testcase': 'dist.rpmdiff.comparison.xml_validity',
            'type': 'test-result-failed'
        },
    ] + [
        {
            'item': nvr,
            'testcase': name,
            'type': 'test-result-missing'
        } for name in all_rpmdiff_testcase_names if name != 'dist.rpmdiff.comparison.xml_validity'
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_make_a_decison_on_no_results(requests_session, greenwave_server, testdatabuilder):
    nvr = testdatabuilder.unique_nvr()
    data = {
        'decision_context': 'errata_newfile_to_qe',
        'product_version': 'rhel-7',
        'subject': [nvr]
    }
    r = requests_session.post(greenwave_server.url + 'api/v1.0/decision',
                              headers={'Content-Type': 'application/json'},
                              data=json.dumps(data))
    assert r.status_code == 200
    res_data = r.json()
    assert res_data['policies_satisified'] is False
    assert res_data['applicable_policies'] == ['1']
    expected_summary = '{}: no test results found'.format(nvr)
    assert res_data['summary'] == expected_summary
    expected_unsatisfied_requirements = [
        {
            'item': nvr,
            'testcase': name,
            'type': 'test-result-missing'
        } for name in all_rpmdiff_testcase_names
    ]
    assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements
