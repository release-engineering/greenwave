
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import json
import requests_mock
from flask import current_app
from mock import patch


def test_cannot_make_decision_without_product_version(client):
    data = {
        'decision_context': 'errta_newfile_to_qe',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = client.post('/api/v1.0/decision', data=json.dumps(data),
                    content_type='application/json')
    assert r.status_code == 400
    assert 'Missing required product version' in r.get_data()


def test_cannot_make_decision_without_decision_context(client):
    data = {
        'product_version': 'rhel-7',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = client.post('/api/v1.0/decision', data=json.dumps(data),
                    content_type='application/json')
    assert r.status_code == 400
    assert 'Missing required decision context' in r.get_data()


def test_cannot_make_decision_without_subject(client):
    data = {
        'decision_context': 'errta_newfile_to_qe',
        'product_version': 'rhel-7',
    }
    r = client.post('/api/v1.0/decision', data=json.dumps(data),
                    content_type='application/json')
    assert r.status_code == 400
    assert 'Missing required subject' in r.get_data()


def test_404_for_inapplicable_policies(client):
    data = {
        'decision_context': 'dummpy_decision',
        'product_version': 'rhel-7',
        'subject': ['foo-1.0.0-1.el7']
    }
    r = client.post('/api/v1.0/decision', data=json.dumps(data),
                    content_type='application/json')
    assert r.status_code == 404
    assert 'Cannot find any applicable policies for %s' % data['product_version'] in r.get_data()


def test_make_a_decison_on_passed_result(client):
    with requests_mock.Mocker() as m:
        mocked_results = {
          "data": [
            {
              "data": {
                   "item": [
                      "foo-1.0.0-2.el7"
                    ]
              },
              "groups": [
                  "5d307e4f-1ade-4c41-9e67-e5a73d5cdd07"
              ],
              "href": "https://resultsdb.domain.local/api/v2.0/results/331284",
              "id": 331284,
              "note": "",
              "outcome": "PASSED",
              "ref_url": "https://rpmdiff.domain.local/run/97683/26",
              "submit_time": "2017-05-19T04:41:13.957729",
              "testcase": {
                "href": 'https://resultsdb.domain.local/api/v2.0/testcases/'
                        'dist.rpmdiff.comparison.xml_validity',
                "name": "dist.rpmdiff.comparison.xml_validity",
                "ref_url": "https://docs.domain.local/display/HTD/rpmdiff-valid-file"
              }
            }
          ]
        }
        m.register_uri('GET', '{}/results?item={}&testcases={}'.format(
            current_app.config['RESULTSDB_API_URL'],
            'foo-1.0.0-2.el7',
            'dist.rpmdiff.comparison.xml_validity'
        ), json=mocked_results)
        dummy_policies = {
            '1': {
                'product_version': 'rhel-7',
                'decision_context': 'dummpy_decision',
                'rules': ['dist.rpmdiff.comparison.xml_validity']
            }
        }
        with patch.dict('greenwave.policies.policies', dummy_policies):
            data = {
                'decision_context': 'dummpy_decision',
                'product_version': 'rhel-7',
                'subject': ['foo-1.0.0-2.el7']
            }
            r = client.post('/api/v1.0/decision', data=json.dumps(data),
                            content_type='application/json')
            assert r.status_code == 200
            res_data = json.loads(r.get_data(as_text=True))
            assert res_data['policies_satisified'] == True
            assert res_data['applicable_policies'] == ['1']
            assert res_data['summary'] == 'foo-1.0.0-2.el7: policy 1 is satisfied as all required' \
                ' tests are passing'


def test_make_a_decison_on_failed_result_with_waiver(client):
    with requests_mock.Mocker() as m:
        mocked_results = {
          "data": [
            {
              "data": {
                   "item": [
                      "foo-1.0.0-2.el7"
                    ]
              },
              "groups": [
                  "5d307e4f-1ade-4c41-9e67-e5a73d5cdd07"
              ],
              "href": "https://resultsdb.domain.local/api/v2.0/results/331284",
              "id": 331284,
              "note": "",
              "outcome": "FAILED",
              "ref_url": "https://rpmdiff.domain.local/run/97683/26",
              "submit_time": "2017-05-19T04:41:13.957729",
              "testcase": {
                "href": 'https://resultsdb.domain.local/api/v2.0/testcases/'
                        'dist.rpmdiff.comparison.xml_validity',
                "name": "dist.rpmdiff.comparison.xml_validity",
                "ref_url": "https://docs.domain.local/display/HTD/rpmdiff-valid-file"
              }
            }
          ]
        }
        m.register_uri('GET', '{}/results?item={}&testcases={}'.format(
            current_app.config['RESULTSDB_API_URL'],
            'foo-1.0.0-2.el7',
            'dist.rpmdiff.comparison.xml_validity'
        ), json=mocked_results)
        mocked_waiver = {
          "data": [
            {
              "id": 1,
              "result_id": 331284,
              "username": 'fool',
              "comment": 'it broke',
              "waived": True,
              "timestamp": '2017-05-17T03:13:31.735858',
              "product_version": 'rhel-7'
            }
          ]
        }
        m.register_uri('GET', '{}/waivers/?result_id={}&project_version={}'.format(
            current_app.config['WAIVERDB_API_URL'],
            331284,
            'rhel-7'
        ), json=mocked_waiver)
        dummy_policies = {
            '1': {
                'product_version': 'rhel-7',
                'decision_context': 'dummpy_decision',
                'rules': ['dist.rpmdiff.comparison.xml_validity']
            }
        }
        with patch.dict('greenwave.policies.policies', dummy_policies):
            data = {
                'decision_context': 'dummpy_decision',
                'product_version': 'rhel-7',
                'subject': ['foo-1.0.0-2.el7']
            }
            r = client.post('/api/v1.0/decision', data=json.dumps(data),
                            content_type='application/json')
            assert r.status_code == 200
            res_data = json.loads(r.get_data(as_text=True))
            assert res_data['policies_satisified'] == True
            assert res_data['applicable_policies'] == ['1']
            assert res_data['summary'] == 'foo-1.0.0-2.el7: policy 1 is satisfied as all required' \
                ' tests are passing'


def test_make_a_decison_on_failed_result(client):
    with requests_mock.Mocker() as m:
        mocked_results = {
          "data": [
            {
              "data": {
                   "item": [
                      "foo-1.0.0-2.el7"
                    ]
              },
              "groups": [
                  "5d307e4f-1ade-4c41-9e67-e5a73d5cdd07"
              ],
              "href": "https://resultsdb.domain.local/api/v2.0/results/331284",
              "id": 331284,
              "note": "",
              "outcome": "FAILED",
              "ref_url": "https://rpmdiff.domain.local/run/97683/26",
              "submit_time": "2017-05-19T04:41:13.957729",
              "testcase": {
                "href": 'https://resultsdb.domain.local/api/v2.0/testcases/'
                        'dist.rpmdiff.comparison.xml_validity',
                "name": "dist.rpmdiff.comparison.xml_validity",
                "ref_url": "https://docs.domain.local/display/HTD/rpmdiff-valid-file"
              }
            }
          ]
        }
        m.register_uri('GET', '{}/results?item={}&testcases={}'.format(
            current_app.config['RESULTSDB_API_URL'],
            'foo-1.0.0-2.el7',
            'dist.rpmdiff.comparison.xml_validity,dist.rpmdiff.comparison.virus_scan'
        ), json=mocked_results)
        m.register_uri('GET', '{}/waivers/?result_id={}&project_version={}'.format(
            current_app.config['WAIVERDB_API_URL'],
            331284,
            'rhel-7'
        ), json={"data": []})
        dummy_policies = {
            '1': {
                'product_version': 'rhel-7',
                'decision_context': 'dummpy_decision',
                'rules': ['dist.rpmdiff.comparison.xml_validity',
                          'dist.rpmdiff.comparison.virus_scan']
            }
        }
        with patch.dict('greenwave.policies.policies', dummy_policies):
            data = {
                'decision_context': 'dummpy_decision',
                'product_version': 'rhel-7',
                'subject': ['foo-1.0.0-2.el7']
            }
            r = client.post('/api/v1.0/decision', data=json.dumps(data),
                            content_type='application/json')
            assert r.status_code == 200
            res_data = json.loads(r.get_data(as_text=True))
            assert res_data['policies_satisified'] == False
            assert res_data['applicable_policies'] == ['1']
            assert res_data['summary'] == 'foo-1.0.0-2.el7: 2 of 2 required tests' \
                ' failed, the policy 1 is not satisfied'
            expected_unsatisfied_requirements = [
                {
                    'item': 'foo-1.0.0-2.el7',
                    'result_id': 331284,
                    'testcase': 'dist.rpmdiff.comparison.xml_validity',
                    'type': 'test-result-failed'
                },
                {
                 'item': 'foo-1.0.0-2.el7',
                 'testcase': 'dist.rpmdiff.comparison.virus_scan',
                 'type': 'test-result-missing'
                }]
            assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements


def test_make_a_decison_on_no_results(client):
    with requests_mock.Mocker() as m:
        m.register_uri('GET', '{}/results?item={}&testcases={}'.format(
            current_app.config['RESULTSDB_API_URL'],
            'foo-1.0.0-2.el7',
            'dist.rpmdiff.comparison.xml_validity'
        ), json={"data": []})
        dummy_policies = {
            '1': {
                'product_version': 'rhel-7',
                'decision_context': 'dummpy_decision',
                'rules': ['dist.rpmdiff.comparison.xml_validity']
            }
        }
        with patch.dict('greenwave.policies.policies', dummy_policies):
            data = {
                'decision_context': 'dummpy_decision',
                'product_version': 'rhel-7',
                'subject': ['foo-1.0.0-2.el7']
            }
            r = client.post('/api/v1.0/decision', data=json.dumps(data),
                            content_type='application/json')
            assert r.status_code == 200
            res_data = json.loads(r.get_data(as_text=True))
            assert res_data['policies_satisified'] == False
            assert res_data['applicable_policies'] == ['1']
            assert res_data['summary'] == 'foo-1.0.0-2.el7: no test results found'
            expected_unsatisfied_requirements = [
                {
                    'item': 'foo-1.0.0-2.el7',
                    'testcase': 'dist.rpmdiff.comparison.xml_validity',
                    'type': 'test-result-missing'
                }]
            assert res_data['unsatisfied_requirements'] == expected_unsatisfied_requirements
