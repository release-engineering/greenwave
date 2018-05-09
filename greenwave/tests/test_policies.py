
# SPDX-License-Identifier: GPL-2.0+

import json
import pytest
import mock

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
        '1 of 1 required test results missing'
    assert summarize_answers([TestResultMissing('item', 'test', None),
                              TestResultFailed('item', 'test', None, 'id')]) == \
        '1 of 2 required tests failed, 1 result missing'
    assert summarize_answers([TestResultMissing('item', 'testa', None),
                              TestResultMissing('item', 'testb', None),
                              TestResultFailed('item', 'test', None, 'id')]) == \
        '1 of 3 required tests failed, 2 results missing'
    assert summarize_answers([TestResultMissing('item', 'test', None), RuleSatisfied()]) == \
        '1 of 2 required test results missing'


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


def test_package_specific_rule(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: "some_policy"
product_versions:
  - rhel-9000
decision_context: compose_gate
blacklist: []
rules:
  - !PackageSpecificBuild {test_case_name: sometest, repos: [nethack, python-*]}
        """)
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    # Ensure that we fail with no results
    item = {'item': 'nethack-1.2.3-1.el9000', 'type': 'koji_build'}
    results, waivers = [], []
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # That a matching, failing result can fail
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    # That a matching, passing result can pass
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'PASSED',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # That a non-matching passing result is ignored.
    item = {'item': 'foobar-1.2.3-1.el9000', 'type': 'koji_build'}
    results = [{
        'id': 123,
        'item': 'foobar-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'PASSED',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # That a non-matching failing result is ignored.
    results = [{
        'id': 123,
        'item': 'foobar-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)  # ooooh.

    # Ensure that fnmatch globs work in absence
    item = {'item': 'python-foobar-1.2.3-1.el9000', 'type': 'koji_build'}
    results, waivers = [], []
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # Ensure that fnmatch globs work in the negative.
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    # Ensure that fnmatch globs work in the positive.
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'SUCCESS',
    }]
    decision = policy.check(item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)


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


def test_product_versions_pattern(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: dummy_policy
product_versions:
  - fedora-*
decision_context: dummy_context
blacklist: []
rules: []
        """)
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    assert policy.applies_to('dummy_context', 'fedora-27')
    assert policy.applies_to('dummy_context', 'fedora-28')
    assert not policy.applies_to('dummy_context', 'epel-7')


def test_remote_original_spec_nvr_rule_policy(tmpdir):
    """ Testing the RemoteOriginalSpecNvrRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = """
--- !Policy
id: "taskotron_release_critical_tasks_with_remoterule"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
blacklist: []
rules:
  - !RemoteOriginalSpecNvrRule {}
        """

    remote_fragment = """
--- !Policy
id: "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
blacklist: []
rules:
  - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_rev_from_koji'):
            with mock.patch('greenwave.resources.retrieve_yaml_remote_original_spec_nvr_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                item, waivers = {'original_spec_nvr': nvr}, []

                # Ensure that presence of a result is success.
                results = [{
                    "id": 12345,
                    "data": {"original_spec_nvr": [nvr]},
                    "testcase": {"name": "dist.upgradepath"},
                    "outcome": "PASSED"
                }]
                decision = policy.check(item, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], RuleSatisfied)

                # Ensure that absence of a result is failure.
                results = []
                decision = policy.check(item, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultMissing)

                # And that a result with a failure, is a failure.
                results = [{
                    "id": 12345,
                    "data": {"original_spec_nvr": [nvr]},
                    "testcase": {"name": "dist.upgradepath"},
                    "outcome": "FAILED"
                }]
                decision = policy.check(item, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultFailed)
