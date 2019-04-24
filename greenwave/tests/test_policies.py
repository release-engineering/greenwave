
# SPDX-License-Identifier: GPL-2.0+

import pytest
import mock

from textwrap import dedent

from greenwave.app_factory import create_app
from greenwave.policies import (
    load_policies,
    summarize_answers,
    Policy,
    RemotePolicy,
    RuleSatisfied,
    TestResultMissing,
    TestResultFailed,
    TestResultPassed,
    InvalidGatingYaml,
    OnDemandPolicy
)
from greenwave.resources import ResultsRetriever
from greenwave.safe_yaml import SafeYAMLError


class DummyResultsRetriever(ResultsRetriever):
    def __init__(
            self, subject_identifier=None, testcase=None, outcome='PASSED',
            subject_type='koji_build'):
        super(DummyResultsRetriever, self).__init__(
            cache=mock.Mock(),
            ignore_results=[],
            when='',
            timeout=0,
            verify=False,
            url='')
        self.subject_identifier = subject_identifier
        self.subject_type = subject_type
        self.testcase = testcase
        self.outcome = outcome

    def _make_request(self, params):
        if (params.get('item') == self.subject_identifier and
                params.get('type') == self.subject_type and
                params.get('testcases') == self.testcase):
            return [{
                'id': 123,
                'data': {
                    'item': [self.subject_identifier],
                    'type': [self.subject_type],
                },
                'testcase': {'name': self.testcase},
                'outcome': self.outcome,
            }]
        return []


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()]) == \
        'All required tests passed'
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
    p.write(dedent("""
        --- !Policy
        id: "rawhide_compose_sync_to_mirrors"
        product_versions:
          - fedora-rawhide
        decision_context: rawhide_compose_sync_to_mirrors
        subject_type: compose
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    # Ensure that absence of a result is failure.
    item, results, waivers = {}, DummyResultsRetriever(), []
    decision = policy.check('fedora-rawhide', item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultMissing)

    # But also that waiving the absence works.
    waivers = [{'testcase': 'sometest', 'waived': True}]
    decision = policy.check('fedora-rawhide', item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)


def test_waive_brew_koji_mismatch(tmpdir):
    """ Ensure that a koji_build waiver can match a brew-build result

    Note that 'brew-build' in the result does not match 'koji_build' in the
    waiver.  Even though these are different strings, this should work.
    """

    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: some_id
        product_versions:
        - fedora-rawhide
        decision_context: test
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    results = DummyResultsRetriever('some_nevr', 'sometest', 'FAILED', 'brew-build')
    waiver = {
        u'subject_identifier': u'some_nevr',
        u'subject_type': u'koji_build',
        u'testcase': u'sometest',
        u'waived': True,
    }

    item, waivers = 'some_nevr', [waiver]
    decision = policy.check('fedora-rawhide', item, results, [])
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    decision = policy.check('fedora-rawhide', item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # Also, be sure that negative waivers work.
    waivers[0]['waived'] = False
    decision = policy.check('fedora-rawhide', item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)


def test_waive_bodhi_update(tmpdir):
    """ Ensure that a koji_build waiver can match a brew-build result

    Note that 'brew-build' in the result does not match 'koji_build' in the
    waiver.  Even though these are different strings, this should work.
    """

    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: some_id
        product_versions:
        - fedora-rawhide
        decision_context: test
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    item = 'some_bodhi_update'
    results = DummyResultsRetriever(item, 'sometest', 'FAILED', 'bodhi_update')
    waivers = [{
        u'subject_identifier': item,
        u'subject_type': 'bodhi_update',
        u'testcase': 'sometest',
        u'waived': True,
    }]

    decision = policy.check('fedora-rawhide', item, results, [])
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultFailed)

    decision = policy.check('fedora-rawhide', item, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)

    # Also, be sure that negative waivers work.
    waivers[0]['waived'] = False
    decision = policy.check('fedora-rawhide', item, results, waivers)
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
    p.write(dedent("""
        ---
        id: "taskotron_release_critical_tasks"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: dist.abicheck}
        """))
    expected_error = "Missing !Policy tag"
    with pytest.raises(SafeYAMLError, match=expected_error):
        load_policies(tmpdir.strpath)


def test_misconfigured_policy_rules(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable
        subject_type: bodhi_update
        rules:
          - {test_case_name: dist.abicheck}
        """))
    expected_error = (
        "Policy 'taskotron_release_critical_tasks': "
        "Attribute 'rules': "
        "Expected list of Rule objects"
    )
    with pytest.raises(SafeYAMLError, match=expected_error):
        load_policies(tmpdir.strpath)


def test_passing_testcasename_with_scenario(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "rawhide_compose_sync_to_mirrors"
        product_versions:
          - fedora-rawhide
        decision_context: rawhide_compose_sync_to_mirrors
        subject_type: compose
        rules:
          - !PassingTestCaseRule {test_case_name: compose.install_default_upload,
          scenario: somescenario}
        """))
    load_policies(tmpdir.strpath)


@pytest.mark.parametrize(('product_version', 'applies'), [
    ('fedora-27', True),
    ('fedora-28', True),
    ('epel-7', False),
])
def test_product_versions_pattern(product_version, applies, tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: dummy_policy
        product_versions:
          - fedora-*
        decision_context: dummy_context
        subject_type: bodhi_update
        rules:
          - !PassingTestCaseRule {test_case_name: test}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    assert applies == policy.matches(
        decision_context='dummy_context',
        product_version=product_version,
        subject_type='bodhi_update')


@pytest.mark.parametrize('namespace', ["rpms", ""])
def test_remote_rule_policy(tmpdir, namespace):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: koji_build
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
        - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = (namespace, 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                waivers = []

                # Ensure that presence of a result is success.
                results = DummyResultsRetriever(nvr, 'dist.upgradepath')
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], RuleSatisfied)

                # Ensure that absence of a result is failure.
                results = DummyResultsRetriever()
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultMissing)

                # And that a result with a failure, is a failure.
                results = DummyResultsRetriever(nvr, 'dist.upgradepath', 'FAILED')
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultFailed)


@pytest.mark.parametrize('namespace', ["modules", ""])
def test_remote_rule_policy_redhat_module(tmpdir, namespace):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = '389-ds-1.4-820181127205924.9edba152'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate
        subject_type: redhat-module
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate
        subject_type: redhat-module
        rules:
          - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-module.tier0.functional}

        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = (namespace, '389-ds', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                waivers = []

                # Ensure that presence of a result is success.
                results = DummyResultsRetriever(nvr, 'baseos-ci.redhat-module.tier0.functional',
                                                subject_type='redhat-module')
                decision = policy.check('rhel-8', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], RuleSatisfied)

                # Ensure that absence of a result is failure.
                results = DummyResultsRetriever(subject_type='redhat-module')
                decision = policy.check('rhel-8', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultMissing)

                # And that a result with a failure, is a failure.
                results = DummyResultsRetriever(nvr, 'baseos-ci.redhat-module.tier0.functional',
                                                'FAILED', subject_type='redhat-module')
                decision = policy.check('rhel-8', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultFailed)


def test_remote_rule_policy_optional_id(tmpdir):
    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: koji_build
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
          - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)
                policy = policies[0]

                results, waivers = [], []
                expected_details = "Policy 'untitled': Attribute 'product_versions' is required"
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], InvalidGatingYaml)
                assert decision[0].is_satisfied is False
                assert decision[0].details == expected_details


def test_remote_rule_malformed_yaml(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: koji_build
        rules:
          - !RemoteRule {}
        """)

    remote_fragments = [dedent("""
        --- !Policy
           : "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        blacklist: []
        rules:
          - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """), dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
          - !RemoteRule {test_case_name: dist.upgradepath}
        """)]

    for remote_fragment in remote_fragments:
        p = tmpdir.join('gating.yaml')
        p.write(serverside_fragment)
        app = create_app('greenwave.config.TestingConfig')
        with app.app_context():
            with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
                scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
                with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                    f.return_value = remote_fragment
                    policies = load_policies(tmpdir.strpath)
                    policy = policies[0]

                    results, waivers = [], []
                    decision = policy.check('fedora-26', nvr, results, waivers)
                    assert len(decision) == 1
                    assert isinstance(decision[0], InvalidGatingYaml)
                    assert decision[0].is_satisfied is False


def test_remote_rule_malformed_yaml_with_waiver(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file
    But this time waiving the error """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: koji_build
        rules:
          - !RemoteRule {}
        """)

    remote_fragments = [dedent("""
        --- !Policy
           : "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        blacklist: []
        rules:
          - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """), dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
          - !RemoteRule {test_case_name: dist.upgradepath}
        """)]

    for remote_fragment in remote_fragments:
        p = tmpdir.join('gating.yaml')
        p.write(serverside_fragment)
        app = create_app('greenwave.config.TestingConfig')
        with app.app_context():
            with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
                scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
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
                    decision = policy.check('fedora-26', nvr, results, waivers)
                    assert len(decision) == 0


def test_parse_policies_missing_tag():
    expected_error = "Missing !Policy tag"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all("""---""")


def test_parse_policies_unexpected_type():
    policies = dedent("""
        --- !Policy
        42
    """)
    expected_error = "Expected mapping for !Policy tagged object"
    with pytest.raises(SafeYAMLError, match=expected_error):
        RemotePolicy.safe_load_all(policies)


def test_parse_policies_missing_id():
    expected_error = "Policy 'untitled': Attribute 'id' is required"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all(dedent("""
            --- !Policy
            product_versions: [fedora-rawhide]
            decision_context: test
            subject_type: compose
            blacklist: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
        """))


def test_parse_policies_missing_product_versions():
    expected_error = "Policy 'test': Attribute 'product_versions' is required"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all(dedent("""
            --- !Policy
            id: test
            decision_context: test
            subject_type: compose
            blacklist: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
        """))


def test_parse_policies_missing_decision_context():
    expected_error = "Policy 'test': Attribute 'decision_context' is required"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            subject_type: compose
            blacklist: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
        """))


def test_policy_with_arbitrary_subject_type(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "some_policy"
        product_versions:
          - rhel-9000
        decision_context: bodhi_update_push_stable
        subject_type: kind-of-magic
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    waivers = []
    results = DummyResultsRetriever('nethack-1.2.3-1.el9000', 'sometest', 'PASSED', 'kind-of-magic')
    decision = policy.check('rhel-9000', 'nethack-1.2.3-1.el9000', results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], TestResultPassed)


@pytest.mark.parametrize(('package', 'num_decisions'), [
    ('nethack', 1),
    ('net*', 1),
    ('python-requests', 0),
])
def test_policy_with_packages_whitelist(tmpdir, package, num_decisions):
    p = tmpdir.join('temp.yaml')
    p.write(dedent("""
        --- !Policy
        id: "some_policy"
        product_versions:
          - rhel-9000
        decision_context: test
        subject_type: koji_build
        packages:
        - {}
        rules:
          - !PassingTestCaseRule {{test_case_name: sometest}}
        """.format(package)))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]

    waivers = []
    results = DummyResultsRetriever('nethack-1.2.3-1.el9000', 'sometest', 'PASSED', 'koji_build')
    decision = policy.check('rhel-9000', 'nethack-1.2.3-1.el9000', results, waivers)
    assert len(decision) == num_decisions
    if num_decisions:
        assert isinstance(decision[0], TestResultPassed)


def test_parse_policies_invalid_rule():
    expected_error = "Policy 'test': Attribute 'rules': Expected list of Rule objects"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            decision_context: test
            subject_type: compose
            blacklist: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
              - bad_rule
        """))


def test_parse_policies_remote_missing_tag():
    expected_error = "Missing !Policy tag"
    with pytest.raises(SafeYAMLError, match=expected_error):
        RemotePolicy.safe_load_all("""---""")


def test_parse_policies_remote_missing_id_is_ok():
    policies = RemotePolicy.safe_load_all(dedent("""
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}
    """))
    assert len(policies) == 1
    assert policies[0].id is None


def test_parse_policies_remote_missing_subject_type_is_ok():
    policies = RemotePolicy.safe_load_all(dedent("""
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}
    """))
    assert len(policies) == 1
    assert policies[0].subject_type == 'koji_build'


def test_parse_policies_remote_recursive():
    expected_error = "Policy 'test': RemoteRule is not allowed in remote policies"
    with pytest.raises(SafeYAMLError, match=expected_error):
        RemotePolicy.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            decision_context: bodhi_update_push_stable_with_remoterule
            subject_type: koji_build
            rules:
              - !RemoteRule {}
        """))


def test_parse_policies_remote_multiple():
    policies = RemotePolicy.safe_load_all(dedent("""
        --- !Policy
        id: test1
        product_versions: [fedora-rawhide]
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}

        --- !Policy
        id: test2
        product_versions: [fedora-rawhide]
        decision_context: test
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}
    """))
    assert len(policies) == 2
    assert policies[0].id == 'test1'
    assert policies[1].id == 'test2'


def test_parse_policies_remote_subject_types():
    policies = RemotePolicy.safe_load_all(dedent("""
        --- !Policy
        id: test1
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}

        --- !Policy
        id: test2
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: redhat-module
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}
    """))
    assert len(policies) == 2
    assert policies[0].id == 'test1'
    assert policies[0].subject_type == 'koji_build'
    assert policies[1].id == 'test2'
    assert policies[1].subject_type == 'redhat-module'


def test_parse_policies_remote_multiple_missing_tag():
    expected_error = "Missing !Policy tag"
    with pytest.raises(SafeYAMLError, match=expected_error):
        RemotePolicy.safe_load_all(dedent("""
            --- !Policy
            id: test1
            product_versions: [fedora-rawhide]
            decision_context: test
            rules:
              - !PassingTestCaseRule {test_case_name: test.case.name}

            ---
            id: test2
            product_versions: [fedora-rawhide]
            decision_context: test
            rules:
              - !PassingTestCaseRule {test_case_name: test.case.name}
        """))


def test_parse_policies_remote_missing_rule_attribute():
    expected_error = (
        "Policy 'test': "
        "Attribute 'rules': "
        "YAML object !PassingTestCaseRule: "
        "Attribute 'test_case_name' is required"
    )
    with pytest.raises(SafeYAMLError, match=expected_error):
        RemotePolicy.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            decision_context: test
            rules:
              - !PassingTestCaseRule {test_case: test.case.name}
        """))


def test_policies_to_json():
    policies = Policy.safe_load_all(dedent("""
        --- !Policy
        id: test
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: compose
        blacklist: []
        excluded_packages: []
        rules: []
    """))
    assert len(policies) == 1
    assert policies[0].to_json() == {
        'id': 'test',
        'product_versions': ['fedora-rawhide'],
        'decision_context': 'test',
        'subject_type': 'compose',
        'blacklist': [],
        'excluded_packages': [],
        'packages': [],
        'rules': [],
        'relevance_key': None,
        'relevance_value': None,
    }


def test_policy_with_subject_type_component_version(tmpdir):
    nv = '389-ds-base-1.4.0.10'
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "test-new-subject-type"
        product_versions:
        - fedora-29
        decision_context: decision_context_test_component_version
        subject_type: component-version
        blacklist: []
        rules:
          - !PassingTestCaseRule {test_case_name: test_for_new_type}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]
    results = DummyResultsRetriever(nv, 'test_for_new_type', 'PASSED',
                                    'component-version')
    waivers = []
    decision = policy.check('fedora-29', nv, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)


def test_policy_with_subject_type_redhat_module(tmpdir):
    nsvc = 'httpd:2.4:20181018085700:9edba152'
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "test-new-subject-type"
        product_versions:
        - fedora-29
        decision_context: decision_context_test_redhat_module
        subject_type: redhat-module
        blacklist: []
        rules:
          - !PassingTestCaseRule {test_case_name: test_for_redhat_module_type}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]
    results = DummyResultsRetriever(nsvc, 'test_for_redhat_module_type', 'PASSED',
                                    'redhat-module')
    waivers = []
    decision = policy.check('fedora-29', nsvc, results, waivers)
    assert len(decision) == 1
    assert isinstance(decision[0], RuleSatisfied)


@pytest.mark.parametrize('namespace', ["rpms", ""])
def test_remote_rule_policy_on_demand_policy(namespace):
    """ Testing the RemoteRule with the koji interaction when on_demand policy is given.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'

    serverside_json = {
        'product_version': 'fedora-26',
        'id': 'taskotron_release_critical_tasks_with_remoterule',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'rules': [
            {
                'type': 'RemoteRule'
            },
        ],
    }

    remote_fragment = dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
        - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = (namespace, 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policy = OnDemandPolicy.create_from_json(serverside_json)  # pylint: disable=W0212
                waivers = []

                # Ensure that presence of a result is success.
                results = DummyResultsRetriever(nvr, 'dist.upgradepath')
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], RuleSatisfied)

                # Ensure that absence of a result is failure.
                results = DummyResultsRetriever()
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultMissing)

                # And that a result with a failure, is a failure.
                results = DummyResultsRetriever(nvr, 'dist.upgradepath', 'FAILED')
                decision = policy.check('fedora-26', nvr, results, waivers)
                assert len(decision) == 1
                assert isinstance(decision[0], TestResultFailed)
