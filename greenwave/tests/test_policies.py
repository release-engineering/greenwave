
# SPDX-License-Identifier: GPL-2.0+

import pytest
import mock

from greenwave.app_factory import create_app
from greenwave.policies import (
    summarize_answers,
    RuleSatisfied,
    TestResultMissing,
    TestResultFailed,
    InvalidGatingYaml
)
from greenwave.utils import load_policies


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()]) == \
        'all required tests passed'
    assert summarize_answers([TestResultFailed('koji_build', 'nvr', 'test', None, 'id'),
                              RuleSatisfied()]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('koji_build', 'nvr', 'test', None)]) == \
        '1 of 1 required test results missing'
    assert summarize_answers([TestResultMissing('koji_build', 'nvr', 'test', None),
                              TestResultFailed('koji_build', 'nvr', 'test', None, 'id')]) == \
        '1 of 2 required tests failed, 1 result missing'
    assert summarize_answers([TestResultMissing('koji_build', 'nvr', 'testa', None),
                              TestResultMissing('koji_build', 'nvr', 'testb', None),
                              TestResultFailed('koji_build', 'nvr', 'test', None, 'id')]) == \
        '1 of 3 required tests failed, 2 results missing'
    assert summarize_answers([TestResultMissing('koji_build', 'nvr', 'test', None),
                             RuleSatisfied()]) == \
        '1 of 2 required test results missing'


def test_waive_absence_of_result(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
--- !Policy
id: "rawhide_compose_sync_to_mirrors"
product_versions:
  - fedora-rawhide
decision_context: rawhide_compose_sync_to_mirrors
subject_type: compose
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
decision_context: bodhi_update_push_stable
subject_type: koji_build
rules:
  - !PackageSpecificBuild {test_case_name: sometest, repos: [nethack, python-*]}
        """)
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    # Ensure that we fail with no results
    results, waivers = [], []
    decision = policy.check('nethack-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # That a matching, failing result can fail
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check('nethack-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    # That a matching, passing result can pass
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'PASSED',
    }]
    decision = policy.check('nethack-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # That a non-matching passing result is ignored.
    results = [{
        'id': 123,
        'item': 'foobar-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'PASSED',
    }]
    decision = policy.check('foobar-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # That a non-matching failing result is ignored.
    results = [{
        'id': 123,
        'item': 'foobar-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check('foobar-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)  # ooooh.

    # Ensure that fnmatch globs work in absence
    results, waivers = [], []
    decision = policy.check('python-foobar-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # Ensure that fnmatch globs work in the negative.
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'FAILED',
    }]
    decision = policy.check('python-foobar-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    # Ensure that fnmatch globs work in the positive.
    results = [{
        'id': 123,
        'item': 'nethack-1.2.3-1.el9000',
        'testcase': {'name': 'sometest'},
        'outcome': 'SUCCESS',
    }]
    decision = policy.check('python-foobar-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)


def test_load_policies():
    app = create_app('greenwave.config.TestingConfig')
    assert len(app.config['policies']) > 0
    assert any(policy.id == 'taskotron_release_critical_tasks'
               for policy in app.config['policies'])
    assert any(policy.decision_context == 'bodhi_update_push_stable'
               for policy in app.config['policies'])
    assert any(getattr(rule, 'test_case_name', None) == 'dist.rpmdeplint'
               for policy in app.config['policies'] for rule in policy.rules)


def test_misconfigured_policies(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write("""
---
id: "taskotron_release_critical_tasks"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable
subject_type: bodhi_update
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
subject_type: bodhi_update
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
subject_type: compose
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
subject_type: bodhi_update
rules: []
        """)
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    assert policy.applies_to('dummy_context', 'fedora-27', 'bodhi_update')
    assert policy.applies_to('dummy_context', 'fedora-28', 'bodhi_update')
    assert not policy.applies_to('dummy_context', 'epel-7', 'bodhi_update')


def test_remote_rule_policy(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = """
--- !Policy
id: "taskotron_release_critical_tasks_with_remoterule"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
subject_type: koji_build
rules:
  - !RemoteRule {}
        """

    remote_fragment = """
--- !Policy
id: "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
rules:
  - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                waivers = []

                # Ensure that presence of a result is success.
                results = [{
                    "id": 12345,
                    "data": {"original_spec_nvr": [nvr]},
                    "testcase": {"name": "dist.upgradepath"},
                    "outcome": "PASSED"
                }]
                decision = policy.check(nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], RuleSatisfied)

                # Ensure that absence of a result is failure.
                results = []
                decision = policy.check(nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultMissing)

                # And that a result with a failure, is a failure.
                results = [{
                    "id": 12345,
                    "data": {"original_spec_nvr": [nvr]},
                    "testcase": {"name": "dist.upgradepath"},
                    "outcome": "FAILED"
                }]
                decision = policy.check(nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultFailed)


def test_remote_rule_policy_optional_id(tmpdir):
    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = """
--- !Policy
id: "taskotron_release_critical_tasks_with_remoterule"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
subject_type: koji_build
rules:
  - !RemoteRule {}
        """

    remote_fragment = """
--- !Policy
decision_context: bodhi_update_push_stable_with_remoterule
rules:
  - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                results, waivers = [], []
                expected_error = (
                    'policy dist-git-gating-policy-untitled-nethack'
                    ' is missing attribute product_versions'
                )
                with pytest.raises(RuntimeError, match=expected_error):
                    policy.check(nvr, results, waivers)


def test_remote_rule_malformed_yaml(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = """
--- !Policy
id: "taskotron_release_critical_tasks_with_remoterule"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
subject_type: koji_build
rules:
  - !RemoteRule {}
        """

    remote_fragments = ["""
--- !Policy
   : "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
blacklist: []
rules:
  - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """, """
--- !Policy
id: "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
rules:
  - !RemoteRule {test_case_name: dist.upgradepath}
        """]

    for remote_fragment in remote_fragments:
        p = tmpdir.join('gating.yaml')
        p.write(serverside_fragment)
        app = create_app('greenwave.config.TestingConfig')
        with app.app_context():
            with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
                scm.return_value = ('rpms', 'nethack')
                with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                    f.return_value = remote_fragment
                    policies = load_policies(tmpdir.strpath)
                    policy = policies[0]

                    results, waivers = [], []
                    decision = policy.check(nvr, results, waivers)
                    assert len(decision) == 1
                    assert isinstance(decision[0], InvalidGatingYaml)
                    assert decision[0].is_satisfied is False


def test_remote_rule_malformed_yaml_with_waiver(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file
    But this time waiving the error """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = """
--- !Policy
id: "taskotron_release_critical_tasks_with_remoterule"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
subject_type: koji_build
rules:
  - !RemoteRule {}
        """

    remote_fragments = ["""
--- !Policy
   : "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
blacklist: []
rules:
  - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """, """
--- !Policy
id: "some-policy-from-a-random-packager"
product_versions:
  - fedora-26
decision_context: bodhi_update_push_stable_with_remoterule
rules:
  - !RemoteRule {test_case_name: dist.upgradepath}
        """]

    for remote_fragment in remote_fragments:
        p = tmpdir.join('gating.yaml')
        p.write(serverside_fragment)
        app = create_app('greenwave.config.TestingConfig')
        with app.app_context():
            with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
                scm.return_value = ('rpms', 'nethack')
                with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                    f.return_value = remote_fragment
                    policies = load_policies(tmpdir.strpath)
                    policy = policies[0]

                    results = []
                    waivers = [{
                        'subject_type': 'koji_build',
                        'subject_identifier': 'nethack-1.2.3-1.el9000',
                        'subject': {'type': 'koji_build', 'item': 'nethack-1.2.3-1.el9000'},
                        'testcase': 'invalid-gating-yaml',
                        'product_version': 'fedora-26',
                        'comment': 'Waiving the invalig gating.yaml file'
                    }]
                    decision = policy.check(nvr, results, waivers)
                    assert len(decision) == 0
