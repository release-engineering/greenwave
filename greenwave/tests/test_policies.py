
# SPDX-License-Identifier: GPL-2.0+

import json
import pytest

from greenwave import __version__
from greenwave.app_factory import create_app
from greenwave.policies import (
    summarize_answers,
    RuleSatisfied,
    TestResultMissing,
    TestResultFailed,
)
from greenwave.utils import load_policies


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()]) == \
        'all required tests passed'
    assert summarize_answers([TestResultFailed('item', 'test', None, 'id'), RuleSatisfied()]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test', None)]) == \
        'no test results found'
    assert summarize_answers([TestResultMissing('item', 'test', None),
                              TestResultFailed('item', 'test', None, 'id')]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test', None), RuleSatisfied()]) == \
        '1 of 2 required tests not found'


def test_waive_absence_of_result(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: "rawhide_compose_sync_to_mirrors"
product_versions:
  - fedora-rawhide
decision_context: rawhide_compose_sync_to_mirrors
blacklist: []
rules:
  - !PassingTestCaseRule {test_case_name: sometest}
        """)
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    # Ensure that absence of a result is failure.
    item, results, waivers = {}, [], []
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # But also that waiving the absence works.
    waivers = [{'testcase': 'sometest', 'waived': True}]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)


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
    assert "No JSON payload in request" in output.data


def test_missing_content_type():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo"}),
    )
    assert output.status_code == 415
    assert "No JSON payload in request" in output.data


def test_missing_product_version():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo"}),
        content_type='application/json'
    )
    assert output.status_code == 400
    assert "Missing required product version" in output.data


def test_missing_decision_context():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({"subject": "foo", "product_version": "f26"}),
        content_type='application/json'
    )
    assert output.status_code == 400
    assert "Missing required decision context" in output.data


def test_missing_subject():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.post(
        '/api/v1.0/decision',
        data=json.dumps({
            "decision_context": "bodhi_push_stable",
            "product_version": "f26"
        }),
        content_type='application/json'
    )
    assert output.status_code == 400
    assert "Missing required subject" in output.data


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
        content_type='application/json'
    )
    assert output.status_code == 400
    assert "Invalid subject, must be a list of items" in output.data


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
        content_type='application/json'
    )
    assert output.status_code == 400
    assert "Invalid subject, must be a list of dicts" in output.data


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
        content_type='application/json'
    )
    assert output.status_code == 404
    assert "Cannot find any applicable policies " \
        "for f26 and bodhi_update_push_stable" in output.data


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
        content_type='application/json'
    )
    assert output.status_code == 404
    assert "Cannot find any applicable policies " \
        "for fedora-26 and bodhi_update_push" in output.data


def test_misconfigured_policies(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
---
id: "taskotron_release_critical_tasks"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable
rules:
  - !PassingTestCaseRule {test_case_name: dist.abicheck}
        """)
    with pytest.raises(RuntimeError) as excinfo:
        load_policies(tmpdir.strpath)
    assert 'Policies are not configured properly' in str(excinfo.value)


def test_misconfigured_policy_rules(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: "taskotron_release_critical_tasks"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable
rules:
  - {test_case_name: dist.abicheck}
        """)
    with pytest.raises(RuntimeError) as excinfo:
        load_policies(tmpdir.strpath)
    assert 'Policies are not configured properly' in str(excinfo.value)


def test_passing_testcasename_with_scenario(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: "rawhide_compose_sync_to_mirrors"
product_versions:
  - fedora-rawhide
decision_context: rawhide_compose_sync_to_mirrors
rules:
  - !PassingTestCaseRule {test_case_name: compose.install_default_upload, scenario: somescenario}
        """)
    load_policies(tmpdir.strpath)


def test_version_endpoint():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.get(
        '/api/v1.0/version',
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 200
    assert '"version": "%s"' % __version__ in output.data


def test_version_endpoint_jsonp():
    app = create_app('greenwave.config.TestingConfig')
    test_app = app.test_client()
    output = test_app.get(
        '/api/v1.0/version?callback=bac123',
        headers={"content-type": "application/json"}
    )
    assert output.status_code == 200
    assert 'bac123' in output.data
    assert '"version": "%s"' % __version__ in output.data
