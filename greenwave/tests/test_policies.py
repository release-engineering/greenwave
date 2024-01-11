
# SPDX-License-Identifier: GPL-2.0+

import pytest
import mock
import time

from textwrap import dedent

from greenwave.app_factory import create_app
from greenwave.decision import Decision
from greenwave.policies import (
    applicable_decision_context_product_version_pairs,
    load_policies,
    summarize_answers,
    Policy,
    RemotePolicy,
    RemoteRule,
    RuleSatisfied,
    TestResultMissing,
    TestResultFailed,
    OnDemandPolicy
)
from greenwave.resources import ResultsRetriever, KojiScmUrlParseError
from greenwave.safe_yaml import SafeYAMLError
from greenwave.subjects.factory import create_subject
from greenwave.waivers import waive_answers
from greenwave.config import TestingConfig, Config
from greenwave.utils import add_to_timestamp


@pytest.fixture(autouse=True)
def app():
    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        yield


def answer_types(answers):
    return [x.to_json()['type'] for x in answers]


class DummyResultsRetriever(ResultsRetriever):
    def __init__(self, subject=None, testcase=None, outcome='PASSED', when=''):
        super(DummyResultsRetriever, self).__init__(
            ignore_ids=[],
            when=when,
            url='')
        self.subject = subject
        self.testcase = testcase
        self.outcome = outcome
        self.external_cache = {}
        self.retrieve_data_called = 0

    def _retrieve_data(self, params):
        self.retrieve_data_called += 1
        if (self.subject and (params.get('item') == self.subject.identifier or
                              params.get('nvr') == self.subject.identifier) and
                ('type' not in params or self.subject.type in params['type'].split(',')) and
                (params.get('testcases') is None or params.get('testcases') == self.testcase)):
            return [{
                'id': 123,
                'data': {
                    'item': [self.subject.identifier],
                    'type': [self.subject.type],
                },
                'testcase': {'name': self.testcase},
                'outcome': self.outcome,
                'submit_time': '2021-03-25T07:26:56.191741',
            }]
        return []

    def get_external_cache(self, key):
        return self.external_cache.get(key)

    def set_external_cache(self, key, value):
        self.external_cache[key] = value


def test_summarize_answers():
    testSubject = create_subject('koji_build', 'nvr')
    testResultPassed = RuleSatisfied()
    testResultFailed = TestResultFailed(testSubject, 'test', None, 1, {})
    testResultMissing = TestResultMissing(testSubject, 'test', None, None)

    assert summarize_answers([testResultPassed]) == \
        'All required tests passed'
    assert summarize_answers([testResultFailed, testResultPassed]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([testResultMissing]) == \
        '1 of 1 required test results missing'
    assert summarize_answers([testResultMissing, testResultFailed]) == \
        '1 of 2 required tests failed, 1 result missing'
    assert summarize_answers([testResultMissing, testResultMissing, testResultFailed]) == \
        '1 of 3 required tests failed, 2 results missing'
    assert summarize_answers([testResultMissing, testResultPassed]) == \
        '1 of 2 required test results missing'


def test_decision_with_missing_result(tmpdir):
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

    subject = create_subject('compose', 'some_nevr')
    results = DummyResultsRetriever()
    decision = Decision('rawhide_compose_sync_to_mirrors', 'fedora-rawhide')

    # Ensure that absence of a result is failure.
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-missing']


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

    subject = create_subject('koji_build', 'some_nevr')
    results = DummyResultsRetriever(subject, 'sometest', 'FAILED')

    # Ensure that absence of a result is failure.
    decision = Decision('test', 'fedora-rawhide')
    decision.check(subject, policies, results)
    answers = waive_answers(decision.answers, [])
    assert answer_types(answers) == ['test-result-failed']

    waivers = [{
        'id': 1,
        'subject_identifier': subject.identifier,
        'subject_type': subject.type,
        'testcase': 'sometest',
        'product_version': 'fedora-rawhide',
        'waived': True,
    }]
    decision = Decision('test', 'fedora-rawhide')
    decision.check(subject, policies, results)
    answers = waive_answers(decision.answers, waivers)
    assert answer_types(answers) == ['test-result-failed-waived']


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

    subject = create_subject('bodhi_update', 'some_bodhi_update')
    results = DummyResultsRetriever(subject, 'sometest', 'FAILED')

    decision = Decision('test', 'fedora-rawhide')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-failed']

    waivers = [{
        'id': 1,
        'subject_identifier': subject.identifier,
        'subject_type': subject.type,
        'testcase': 'sometest',
        'product_version': 'fedora-rawhide',
        'waived': True,
    }]
    decision = Decision('test', 'fedora-rawhide')
    decision.check(subject, policies, results)
    answers = waive_answers(decision.answers, waivers)
    assert answer_types(answers) == ['test-result-failed-waived']


def test_load_policies():
    app = create_app('greenwave.config.TestingConfig')
    assert len(app.config['policies']) > 0
    assert any(policy.id == 'taskotron_release_critical_tasks'
               for policy in app.config['policies'])
    assert any(policy.decision_context == 'bodhi_update_push_stable'
               for policy in app.config['policies'])
    assert any(policy.all_decision_contexts == ['bodhi_update_push_stable']
               for policy in app.config['policies'])
    assert any(getattr(rule, 'test_case_name', None) == 'dist.rpmdeplint'
               for policy in app.config['policies'] for rule in policy.rules)


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

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = (namespace, 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(subject, 'dist.upgradepath')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever()
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(subject, 'dist.upgradepath', 'FAILED')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']
            f.assert_called_with(
                'https://src.fedoraproject.org/{0}'.format(
                    '' if not namespace else namespace + '/'
                ) + 'nethack/raw/c3c47a08a66451cb9686c49f040776ed35a0d1bb/f/gating.yaml'
            )


def test_remote_rule_policy_old_config(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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

    config_remote_rules_backup = Config.REMOTE_RULE_POLICIES

    try:
        delattr(Config, 'REMOTE_RULE_POLICIES')

        config = TestingConfig()
        config.DIST_GIT_BASE_URL = 'http://localhost.localdomain/'
        config.DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}{pkg_name}/{rev}/gating.yaml'

        app = create_app(config)

        with app.app_context():
            with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
                scm.return_value = (
                    'rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb'
                )
                with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                    f.return_value = remote_fragment
                    policies = load_policies(tmpdir.strpath)

                    # Ensure that presence of a result is success.
                    results = DummyResultsRetriever(subject, 'dist.upgradepath')
                    decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
                    decision.check(subject, policies, results)
                    assert answer_types(decision.answers) == [
                        'fetched-gating-yaml', 'test-result-passed']

                    call = mock.call(
                        'http://localhost.localdomain/nethack/'
                        'c3c47a08a66451cb9686c49f040776ed35a0d1bb/gating.yaml'
                    )
                    assert f.mock_calls == [call]
    finally:
        Config.REMOTE_RULE_POLICIES = config_remote_rules_backup


def test_remote_rule_policy_brew_build_group(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    subject = create_subject(
        'brew-build-group',
        'sha256:0f41e56a1c32519e189ddbcb01d2551e861bd74e603d01769ef5f70d4b30a2dd'
    )
    namespace = 'rpms'

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-26
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: brew-build-group
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-26
        subject_type: brew-build-group
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
        - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = (namespace, 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(subject, 'dist.upgradepath')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever()
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(subject, 'dist.upgradepath', 'FAILED')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']
            f.assert_called_with(
                'https://git.example.com/devops/greenwave-policies/side-tags/raw/'
                'master/0f41e56a1c32519e189ddbcb01d2551e861bd74e603d01769ef5f70d4b30a2dd.yaml'
            )
        scm.assert_not_called()


def test_remote_rule_policy_with_no_remote_rule_policies_param_defined(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    But this time let's assume that REMOTE_RULE_POLICIES is not defined. """

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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
    app = create_app('greenwave.config.FedoraTestingConfig')

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)

                # Ensure that presence of a result is success.
                results = DummyResultsRetriever(subject, 'dist.upgradepath')
                decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
                decision.check(subject, policies, results)
                assert answer_types(decision.answers) == [
                    'fetched-gating-yaml', 'test-result-passed']
                f.assert_called_with(
                    'https://src.fedoraproject.org/rpms/nethack/raw/'
                    'c3c47a08a66451cb9686c49f040776ed35a0d1bb/f/gating.yaml'
                )


@pytest.mark.parametrize('namespace', ["modules", ""])
def test_remote_rule_policy_redhat_module(tmpdir, namespace):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = '389-ds-1.4-820181127205924.9edba152'
    subject = create_subject('redhat-module', nvr)

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
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = (namespace, '389-ds', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(subject, 'baseos-ci.redhat-module.tier0.functional')
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever(subject)
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(
                subject, 'baseos-ci.redhat-module.tier0.functional', 'FAILED')
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']


def test_remote_rule_policy_redhat_container_image(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = '389-ds-1.4-820181127205924.9edba152'
    subject = create_subject('redhat-container-image', nvr)

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate
        subject_type: redhat-container-image
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate
        subject_type: redhat-container-image
        rules:
          - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-container-image.tier0.functional}

        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('containers', '389-ds', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(
                subject, 'baseos-ci.redhat-container-image.tier0.functional')
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever(subject)
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(
                subject, 'baseos-ci.redhat-container-image.tier0.functional', 'FAILED')
            decision = Decision('osci_compose_gate', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']


def test_remote_rule_with_multiple_contexts(tmpdir):
    """ Testing the RemoteRule with the koji interaction.
    In this case we are just mocking koji """

    nvr = '389-ds-1.4-820181127205924.9edba152'
    subject = create_subject('redhat-container-image', nvr)

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - rhel-8
        decision_contexts:
          - osci_compose_gate1
          - osci_compose_gate2
        subject_type: redhat-container-image
        rules:
          - !RemoteRule {}
        """)

    remote_fragment = dedent("""
        --- !Policy
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate1
        subject_type: redhat-container-image
        rules:
          - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-container-image.tier0.functional}

        --- !Policy
        product_versions:
          - rhel-8
        decision_context: osci_compose_gate2
        subject_type: redhat-container-image
        rules:
          - !PassingTestCaseRule {test_case_name: baseos-ci.redhat-container-image.tier1.functional}

        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('containers', '389-ds', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)
            results = DummyResultsRetriever(
                subject, 'baseos-ci.redhat-container-image.tier0.functional')
            decision = Decision('osci_compose_gate1', 'rhel-8')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']


def test_get_sub_policies_multiple_urls(tmpdir, requests_mock):
    """ Testing the RemoteRule with the koji interaction when on_demand policy is given.
    In this case we are just mocking koji """

    config = TestingConfig()
    config.REMOTE_RULE_POLICIES = {'*': [
        'https://src1.fp.org/{pkg_namespace}{pkg_name}/raw/{rev}/f/gating.yaml',
        'https://src2.fp.org/{pkg_namespace}{pkg_name}/raw/{rev}/f/gating.yaml'
    ]}

    app = create_app(config)

    nvr = 'nethack-1.2.3-1.el9000'
    subject = create_subject('koji_build', nvr)

    serverside_json = {
        'product_version': 'fedora-26',
        'id': 'taskotron_release_critical_tasks_with_remoterule',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'rules': [
            {
                'type': 'RemoteRule',
                'required': True
            },
        ],
    }

    with app.app_context():
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            urls = [
                'https://src{0}.fp.org/{1}/{2}/raw/{3}/f/gating.yaml'.format(i, *scm.return_value)
                for i in range(1, 3)
            ]
            for url in urls:
                requests_mock.head(url, status_code=404)

            policy = OnDemandPolicy.create_from_json(serverside_json)
            assert isinstance(policy.rules[0], RemoteRule)
            assert policy.rules[0].required

            results = DummyResultsRetriever()
            decision = Decision(None, 'fedora-26')
            decision.check(subject, [policy], results)
            request_history = [(r.method, r.url) for r in requests_mock.request_history]
            assert request_history == [('HEAD', urls[0]), ('HEAD', urls[1])]
            assert answer_types(decision.answers) == ['missing-gating-yaml']
            assert not decision.answers[0].is_satisfied
            assert decision.answers[0].subject.identifier == subject.identifier


def test_get_sub_policies_scm_error(tmpdir):
    """
    Test that _get_sub_policies correctly returns an error to go in
    the response - but doesn't raise an exception - when SCM URL parse
    fails.
    """

    nvr = '389-ds-1.4-820181127205924.9edba152'
    subject = create_subject('redhat-container-image', nvr)

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - rhel-8
        decision_contexts:
          - osci_compose_gate1
          - osci_compose_gate2
        subject_type: redhat-container-image
        rules:
          - !RemoteRule {}
        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.side_effect = KojiScmUrlParseError("Failed to parse SCM URL")
        policies = load_policies(tmpdir.strpath)
        results = DummyResultsRetriever(
            subject, 'baseos-ci.redhat-container-image.tier0.functional')
        decision = Decision('osci_compose_gate1', 'rhel-8')
        decision.check(subject, policies, results)
        assert answer_types(decision.answers) == ['failed-fetch-gating-yaml']
        assert not decision.answers[0].is_satisfied
        assert decision.answers[0].subject.identifier == subject.identifier


def test_redhat_container_image_subject_type():
    nvr = '389-ds-1.4-820181127205924.9edba152'
    rdb_url = 'http://results.db'
    cur_time = time.strftime('%Y-%m-%dT%H:%M:%S.00')
    testcase_name = 'testcase1'
    rh_img_subject = create_subject('redhat-container-image', nvr)
    retriever = ResultsRetriever(ignore_ids=list(), when=cur_time, url=rdb_url)
    with mock.patch('requests.Session.get') as req_get:
        req_get.json.return_value = {'data': {'item': [nvr]}}
        retriever._retrieve_all(rh_img_subject, testcase_name)  # pylint: disable=W0212
        assert req_get.call_count == 2
        assert req_get.call_args_list[0] == mock.call(
            f'{rdb_url}/results/latest',
            params={'nvr': nvr,
                    'type': 'redhat-container-image',
                    '_distinct_on': 'scenario,system_architecture,system_variant',
                    'since': f'1900-01-01T00:00:00.000000,{cur_time}',
                    'testcases': testcase_name}
        )
        assert req_get.call_args_list[1] == mock.call(
            f'{rdb_url}/results/latest',
            params={'item': nvr,
                    'type': 'koji_build',
                    '_distinct_on': 'scenario,system_architecture,system_variant',
                    'since': f'1900-01-01T00:00:00.000000,{cur_time}',
                    'testcases': testcase_name}
        )


def test_remote_rule_policy_optional_id(tmpdir):
    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            results = DummyResultsRetriever()
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']
            assert decision.answers[1].is_satisfied is False


def test_remote_rule_malformed_yaml(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file """

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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
        excluded_packages: []
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
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)

                results = DummyResultsRetriever()
                decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
                decision.check(subject, policies, results)
                assert answer_types(decision.answers) == [
                    'fetched-gating-yaml', 'invalid-gating-yaml']
                assert decision.answers[0].is_satisfied is True
                assert decision.answers[1].is_satisfied is False


def test_remote_rule_malformed_yaml_with_waiver(tmpdir):
    """ Testing the RemoteRule with a malformed gating.yaml file
    But this time waiving the error """

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

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
        excluded_packages: []
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
        with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
            scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
            with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
                f.return_value = remote_fragment
                policies = load_policies(tmpdir.strpath)

                results = DummyResultsRetriever()
                waivers = [{
                    'id': 1,
                    'subject_type': 'koji_build',
                    'subject_identifier': 'nethack-1.2.3-1.el9000',
                    'subject': {'type': 'koji_build', 'item': 'nethack-1.2.3-1.el9000'},
                    'testcase': 'invalid-gating-yaml',
                    'product_version': 'fedora-26',
                    'comment': 'Waiving the invalid gating.yaml file',
                    'waived': True,
                }]

                decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-26')
                decision.check(subject, policies, results)
                answers = decision.answers
                assert answer_types(answers) == ['fetched-gating-yaml', 'invalid-gating-yaml']
                answers = waive_answers(answers, waivers)
                assert answer_types(answers) == ['fetched-gating-yaml']


def test_remote_rule_required():
    """ Testing the RemoteRule with required flag set """
    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = None
            policies = Policy.safe_load_all(dedent("""
                --- !Policy
                id: test
                product_versions: [fedora-rawhide]
                decision_context: test
                subject_type: koji_build
                rules:
                  - !RemoteRule {required: true}
            """))
            results = DummyResultsRetriever()
            decision = Decision('test', 'fedora-rawhide')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['missing-gating-yaml']
            assert not decision.answers[0].is_satisfied
            assert decision.answers[0].subject.identifier == subject.identifier


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
            excluded_packages: []
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
            excluded_packages: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
        """))


@pytest.mark.parametrize('policy_class', [Policy, RemotePolicy])
def test_parse_policies_missing_decision_context(policy_class):
    expected_error = "No decision contexts provided"
    with pytest.raises(SafeYAMLError, match=expected_error):
        policy_class.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            subject_type: compose
            excluded_packages: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
        """))


@pytest.mark.parametrize('policy_class', [Policy, RemotePolicy])
def test_parse_policies_both_decision_contexts_set(policy_class):
    expected_error = 'Both properties "decision_contexts" and "decision_context" were set'
    with pytest.raises(SafeYAMLError, match=expected_error):
        policy_class.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            subject_type: compose
            excluded_packages: []
            decision_context: test1
            decision_contexts:
            - test1
            - test2
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
    subject = create_subject('kind-of-magic', 'nethack-1.2.3-1.el9000')
    results = DummyResultsRetriever(subject, 'sometest', 'PASSED')
    decision = Decision('bodhi_update_push_stable', 'rhel-9000')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-passed']


def test_policy_all_decision_contexts(tmpdir):
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "some_policy1"
        product_versions:
          - rhel-9000
        decision_contexts:
          - test1
          - test2
          - test3
        subject_type: kind-of-magic
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}

        --- !Policy
        id: "some_policy2"
        product_versions:
          - rhel-9000
        decision_context: test4
        subject_type: kind-of-magic
        rules:
          - !PassingTestCaseRule {test_case_name: sometest}
        """))
    policies = load_policies(tmpdir.strpath)
    policy = policies[0]
    assert len(policy.all_decision_contexts) == 3
    assert set(policy.all_decision_contexts) == {'test1', 'test2', 'test3'}
    policy = policies[1]
    assert len(policy.all_decision_contexts) == 1
    assert policy.all_decision_contexts == ['test4']


def test_decision_multiple_contexts(tmpdir):
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

        --- !Policy
        id: "some_other_policy"
        product_versions:
          - rhel-9000
        decision_context: some_other_context
        subject_type: kind-of-magic
        rules:
          - !PassingTestCaseRule {test_case_name: someothertest}
        """))
    policies = load_policies(tmpdir.strpath)
    subject = create_subject('kind-of-magic', 'nethack-1.2.3-1.el9000')
    results = DummyResultsRetriever(subject, 'sometest', 'PASSED')
    decision = Decision(['bodhi_update_push_stable', 'some_other_context'], 'rhel-9000')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-passed', 'test-result-missing']


@pytest.mark.parametrize(('package', 'expected_answers'), [
    ('nethack', ['test-result-passed']),
    ('net*', ['test-result-passed']),
    ('python-requests', []),
])
def test_policy_with_packages_allowlist(tmpdir, package, expected_answers):
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
    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')
    results = DummyResultsRetriever(subject, 'sometest', 'PASSED')
    decision = Decision('test', 'rhel-9000')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == expected_answers


def test_parse_policies_invalid_rule():
    expected_error = "Policy 'test': Attribute 'rules': Expected list of Rule objects"
    with pytest.raises(SafeYAMLError, match=expected_error):
        Policy.safe_load_all(dedent("""
            --- !Policy
            id: test
            product_versions: [fedora-rawhide]
            decision_context: test
            subject_type: compose
            excluded_packages: []
            rules:
              - !PassingTestCaseRule {test_case_name: compose.cloud.all}
              - bad_rule
        """))


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


def test_parse_policies_remote_decision_contexts():
    policies = RemotePolicy.safe_load_all(dedent("""
        --- !Policy
        product_versions: [fedora-rawhide]
        decision_contexts: [test1, test2]
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: test.case.name}
    """))
    assert len(policies) == 1
    assert policies[0].all_decision_contexts == ["test1", "test2"]


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


def test_parse_policies_remote_minimal():
    policies = RemotePolicy.safe_load_all(dedent("""
        id: test1
        decision_context: test
        rules: []
    """))
    assert len(policies) == 1
    assert policies[0].id == 'test1'
    assert policies[0].rules == []


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
        excluded_packages: []
        rules: []
    """))
    assert len(policies) == 1
    assert policies[0].to_json() == {
        'id': 'test',
        'product_versions': ['fedora-rawhide'],
        'decision_context': 'test',
        'decision_contexts': [],
        'subject_type': 'compose',
        'excluded_packages': [],
        'packages': [],
        'rules': [],
        'relevance_key': None,
        'relevance_value': None,
    }


def test_policy_with_subject_type_component_version(tmpdir):
    nv = '389-ds-base-1.4.0.10'
    subject = create_subject('component-version', nv)
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "test-new-subject-type"
        product_versions:
        - fedora-29
        decision_context: decision_context_test_component_version
        subject_type: component-version
        excluded_packages: []
        rules:
          - !PassingTestCaseRule {test_case_name: test_for_new_type}
        """))
    policies = load_policies(tmpdir.strpath)
    results = DummyResultsRetriever(subject, 'test_for_new_type', 'PASSED')
    decision = Decision('decision_context_test_component_version', 'fedora-29')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-passed']


@pytest.mark.parametrize('subject_type', ["redhat-module", "redhat-container-image"])
def test_policy_with_subject_type_redhat_module(tmpdir, subject_type):
    nsvc = 'httpd:2.4:20181018085700:9edba152'
    subject = create_subject(subject_type, nsvc)
    p = tmpdir.join('fedora.yaml')
    p.write(dedent("""
        --- !Policy
        id: "test-new-subject-type"
        product_versions:
        - fedora-29
        decision_context: decision_context_test_redhat_module
        subject_type: %s
        excluded_packages: []
        rules:
          - !PassingTestCaseRule {test_case_name: test_for_redhat_module_type}
        """ % subject_type))
    policies = load_policies(tmpdir.strpath)
    results = DummyResultsRetriever(subject, 'test_for_redhat_module_type', 'PASSED')
    decision = Decision('decision_context_test_redhat_module', 'fedora-29')
    decision.check(subject, policies, results)
    assert answer_types(decision.answers) == ['test-result-passed']


@pytest.mark.parametrize('namespace', ["rpms", ""])
def test_remote_rule_policy_on_demand_policy(namespace):
    """ Testing the RemoteRule with the koji interaction when on_demand policy is given.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'
    subject = create_subject('koji_build', nvr)

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
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
        - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = (namespace, 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policy = OnDemandPolicy.create_from_json(serverside_json)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(subject, 'dist.upgradepath')
            decision = Decision(None, 'fedora-26')
            decision.check(subject, [policy], results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever()
            decision = Decision(None, 'fedora-26')
            decision.check(subject, [policy], results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(subject, 'dist.upgradepath', 'FAILED')
            decision = Decision(None, 'fedora-26')
            decision.check(subject, [policy], results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']


@pytest.mark.parametrize('two_rules', (True, False))
def test_on_demand_policy_match(two_rules, koji_proxy):
    """ Proceed other rules when there's no source URL in Koji build """

    nvr = 'httpd-2.4.el9000'
    subject = create_subject('koji_build', nvr)

    serverside_json = {
        'product_version': 'fedora-30',
        'id': 'taskotron_release_critical_tasks_with_remoterule',
        'subject_type': 'koji_build',
        'subject_identifier': nvr,
        'rules': [
            {
                'type': 'RemoteRule'
            }
        ],
    }

    if two_rules:
        serverside_json['rules'].append({
            "type": "PassingTestCaseRule",
            "test_case_name": "fake.testcase.tier0.validation"
        })

    koji_proxy.getBuild.return_value = {'extra': {'source': None}}
    policy = OnDemandPolicy.create_from_json(serverside_json)

    policy_matches = policy.matches(subject=subject)

    koji_proxy.getBuild.assert_called_once()
    assert policy_matches

    results = DummyResultsRetriever(
        subject, 'fake.testcase.tier0.validation', 'PASSED'
    )
    decision = Decision(None, 'fedora-30')
    decision.check(subject, [policy], results)
    if two_rules:
        assert answer_types(decision.answers) == ['test-result-passed']


def test_remote_rule_policy_on_demand_policy_required():
    """ Testing the RemoteRule with the koji interaction when on_demand policy is given.
    In this case we are just mocking koji """

    nvr = 'nethack-1.2.3-1.el9000'
    subject = create_subject('koji_build', nvr)

    serverside_json = {
        'product_version': 'fedora-26',
        'id': 'taskotron_release_critical_tasks_with_remoterule',
        'subject': [{'item': nvr, 'type': 'koji_build'}],
        'rules': [
            {
                'type': 'RemoteRule',
                'required': True
            },
        ],
    }

    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('rpms', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = None

            policy = OnDemandPolicy.create_from_json(serverside_json)
            assert len(policy.rules) == 1
            assert isinstance(policy.rules[0], RemoteRule)
            assert policy.rules[0].required

            results = DummyResultsRetriever()
            decision = Decision(None, 'fedora-26')
            decision.check(subject, [policy], results)
            assert answer_types(decision.answers) == ['missing-gating-yaml']
            assert not decision.answers[0].is_satisfied
            assert decision.answers[0].subject.identifier == subject.identifier


def test_two_rules_no_duplicate(tmpdir):
    nvr = 'nethack-1.2.3-1.el9000'
    subject = create_subject('koji_build', nvr)

    serverside_fragment = dedent("""
        --- !Policy
        id: "taskotron_release_critical_tasks_with_remoterule"
        product_versions:
          - fedora-31
        decision_context: bodhi_update_push_stable_with_remoterule
        subject_type: koji_build
        rules:
          - !RemoteRule {}
          - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    remote_fragment = dedent("""
        --- !Policy
        id: "some-policy-from-a-random-packager"
        product_versions:
          - fedora-31
        decision_context: bodhi_update_push_stable_with_remoterule
        rules:
          - !PassingTestCaseRule {test_case_name: dist.upgradepath}
        """)

    p = tmpdir.join('gating.yaml')
    p.write(serverside_fragment)
    with mock.patch('greenwave.resources.retrieve_scm_from_koji') as scm:
        scm.return_value = ('rmps', 'nethack', 'c3c47a08a66451cb9686c49f040776ed35a0d1bb')
        with mock.patch('greenwave.resources.retrieve_yaml_remote_rule') as f:
            f.return_value = remote_fragment
            policies = load_policies(tmpdir.strpath)

            # Ensure that presence of a result is success.
            results = DummyResultsRetriever(subject, 'dist.upgradepath')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-31')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-passed']

            # Ensure that absence of a result is failure.
            results = DummyResultsRetriever()
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-31')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-missing']

            # And that a result with a failure, is a failure.
            results = DummyResultsRetriever(subject, 'dist.upgradepath', 'FAILED')
            decision = Decision('bodhi_update_push_stable_with_remoterule', 'fedora-31')
            decision.check(subject, policies, results)
            assert answer_types(decision.answers) == ['fetched-gating-yaml', 'test-result-failed']


def test_cache_all_results_temporarily():
    """
    All results are stored in temporary cache (valid during single request).
    """
    subject = create_subject('bodhi_update', 'update-1')
    results = DummyResultsRetriever(subject, 'sometest', 'FAILED')

    retrieved = results.retrieve(subject, testcase=None)
    assert results.retrieve_data_called == 1
    assert retrieved

    cached = results.retrieve(subject, testcase='sometest')
    assert results.retrieve_data_called == 1
    assert cached == retrieved


def test_cache_passing_results():
    """
    Passing results are stored in external cache because it's not expected that
    the outcome changes once they passed.
    """
    subject = create_subject('bodhi_update', 'update-1')
    results = DummyResultsRetriever(subject, 'sometest', 'FAILED')

    retrieved = results.retrieve(subject, testcase=None)
    assert results.retrieve_data_called == 1
    assert retrieved

    results2 = DummyResultsRetriever(subject, 'sometest', 'PASSED')
    results2.external_cache = results.external_cache
    retrieved2 = results2.retrieve(subject, testcase='sometest')
    assert results2.retrieve_data_called == 1
    assert retrieved2
    assert retrieved2 != retrieved

    # Result stays PASSED even if the latest is now FAILED.
    results3 = DummyResultsRetriever(subject, 'sometest', 'FAILED')
    results3.external_cache = results.external_cache
    cached = results3.retrieve(subject, testcase='sometest')
    assert results3.retrieve_data_called == 0
    assert cached == retrieved2

    # Match submit_time with "since" parameter.
    when1 = retrieved2[0]['submit_time']
    when2 = add_to_timestamp(when1, microseconds=1)

    results3 = DummyResultsRetriever(subject, 'sometest', 'FAILED', when=when1)
    results3.external_cache = results.external_cache
    not_cached = results3.retrieve(subject, testcase='sometest')
    assert results3.retrieve_data_called == 1
    assert not_cached == retrieved

    results4 = DummyResultsRetriever(subject, 'sometest', 'FAILED', when=when2)
    results4.external_cache = results.external_cache
    cached = results4.retrieve(subject, testcase='sometest')
    assert results4.retrieve_data_called == 0
    assert cached == retrieved2


def test_applicable_policies():
    policies = Policy.safe_load_all(dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: test_context
        subject_type: koji_build
        rules:
            - !RemoteRule {required: false}
            - !PassingTestCaseRule {test_case_name: common.test.case}
    """))
    remote_fragment = dedent("""
        --- !Policy
        product_versions:
          - fedora-rawhide
        decision_context: test_context
        subject_type: brew-build
        rules:
          - !PassingTestCaseRule {test_case_name: remote.test.case}
    """)

    subject = create_subject('koji_build', 'nethack-1.2.3-1.el9000')

    with mock.patch("greenwave.resources.retrieve_scm_from_koji") as scm:
        scm.return_value = (
            "rpms", "nethack", "c3c47a08a66451cb9686c49f040776ed35a0d1bb")
        with mock.patch("greenwave.resources.retrieve_yaml_remote_rule") as f:
            f.return_value = remote_fragment
            result = applicable_decision_context_product_version_pairs(
                policies,
                subject=subject,
                testcase="remote.test.case",
            )

    assert len(result) == 1
