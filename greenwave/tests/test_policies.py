
# SPDX-License-Identifier: GPL-2.0+

import pytest

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
