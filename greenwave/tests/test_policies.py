
# SPDX-License-Identifier: GPL-2.0+

import json

from greenwave.app_factory import create_app
from greenwave.policies import summarize_answers, RuleSatisfied, TestResultMissing, TestResultFailed


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()]) == \
        'all required tests passed'
    assert summarize_answers([TestResultFailed('item', 'test', 'id'), RuleSatisfied()]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test')]) == \
        'no test results found'
    assert summarize_answers([TestResultMissing('item', 'test'),
                              TestResultFailed('item', 'test', 'id')]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test'), RuleSatisfied()]) == \
        '1 of 2 required tests not found'


def test_load_policies():
    app = create_app('greenwave.config.TestingConfig')
    assert len(app.config['policies']) > 0
    assert any(policy.id == '1' for policy in app.config['policies'])
    assert any(policy.decision_context == 'errata_newfile_to_qe' for policy in
               app.config['policies'])
    assert any(rule.test_case_name == 'dist.rpmdiff.analysis.abi_symbols' for policy in
               app.config['policies'] for rule in policy.rules)


def test_invalid_payload():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post('/api/v1.0/decision', data='not a json')
    assert output.status_code == 415
    assert output.data == '{\n  "message": "No JSON payload in request"\n}\n'


def test_missing_content_type():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo"}),
    )
    assert output.status_code == 415
    assert output.data == '{\n  "message": "No JSON payload in request"\n}\n'


def test_missing_product_version():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo"}),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 400
    assert output.data == '{\n  "message": "Missing required product version"\n}\n'



def test_missing_decision_context():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo", "product_version": "f26"}),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 400
    assert output.data == '{\n  "message": "Missing required decision context"\n}\n'


def test_missing_subject():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_push_stable",
            "product_version": "f26"
        }),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 400
    assert output.data == '{\n  "message": "Missing required subject"\n}\n'


def test_invalid_subect_list():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_push_stable",
            "product_version": "f26",
            "subject": "foo",
        }),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 400
    assert output.data == '{\n  "message": "Invalid subject, must be a list of items"\n}\n'


def test_invalid_subect_list_content():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_update_push_stable",
            "product_version": "fedora-26",
            "subject": ["foo"],
        }),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 400
    assert output.data == '{\n  "message": "Invalid subject, must be a list of dicts"\n}\n'


def test_invalid_product_version():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_update_push_stable",
            "product_version": "f26",
            "subject": ["foo"],
        }),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 404
    assert output.data == '{\n  "message": "Cannot find any applicable '\
        'policies for f26 and bodhi_update_push_stable"\n}\n'


def test_invalid_decision_context():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_update_push",
            "product_version": "fedora-26",
            "subject": ["foo"],
        }),
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 404
    assert output.data == '{\n  "message": "Cannot find any applicable '\
    'policies for fedora-26 and bodhi_update_push"\n}\n'
