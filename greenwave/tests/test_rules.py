import mock
import pytest

from textwrap import dedent

from werkzeug.exceptions import NotFound

from greenwave.app_factory import create_app
from greenwave.decision import Decision
from greenwave.policies import Policy, RemoteRule
from greenwave.resources import NoSourceException
from greenwave.safe_yaml import SafeYAMLError
from greenwave.subjects.factory import create_subject


def test_match_passing_test_case_rule():
    policy_yaml = dedent("""
        --- !Policy
        id: "some_policy"
        product_versions: [rhel-9000]
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: some_test_case}
    """)
    policies = Policy.safe_load_all(policy_yaml)
    assert len(policies) == 1

    policy = policies[0]
    assert len(policy.rules) == 1

    rule = policy.rules[0]
    assert rule.matches(policy)
    assert rule.matches(policy, testcase='some_test_case')
    assert not rule.matches(policy, testcase='other_test_case')


@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
def test_match_remote_rule(mock_retrieve_scm_from_koji, mock_retrieve_yaml_remote_rule):
    policy_yaml = dedent("""
        --- !Policy
        id: "some_policy"
        product_versions: [rhel-9000]
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)
    mock_retrieve_yaml_remote_rule.return_value = dedent("""
        --- !Policy
        product_versions: [rhel-*]
        decision_context: bodhi_update_push_stable
        rules:
          - !PassingTestCaseRule {test_case_name: some_test_case}
    """)
    nvr = 'nethack-1.2.3-1.el9000'
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr, '123')

    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        subject = create_subject('koji_build', nvr)
        policies = Policy.safe_load_all(policy_yaml)
        assert len(policies) == 1

        policy = policies[0]
        assert len(policy.rules) == 1

        rule = policy.rules[0]
        assert rule.matches(policy)
        assert rule.matches(policy, subject=subject)
        assert rule.matches(policy, subject=subject, testcase='some_test_case')
        assert not rule.matches(policy, subject=subject, testcase='other_test_case')


@mock.patch('greenwave.resources.retrieve_yaml_remote_rule')
@mock.patch('greenwave.resources.retrieve_scm_from_koji')
def test_remote_rule_include_failures(
        mock_retrieve_scm_from_koji, mock_retrieve_yaml_remote_rule):
    policy_yaml = dedent("""
        --- !Policy
        id: "some_policy"
        product_versions: [rhel-9000]
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)
    nvr = 'nethack-1.2.3-1.el9000'
    mock_retrieve_scm_from_koji.return_value = ('rpms', nvr, '123')

    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        subject = create_subject('koji_build', nvr)
        policies = Policy.safe_load_all(policy_yaml)
        assert len(policies) == 1

        policy = policies[0]
        assert len(policy.rules) == 1

        rule = policy.rules[0]

        # Include any failure fetching/parsing remote rule file in the
        # decision.
        mock_retrieve_yaml_remote_rule.return_value = "--- !Policy"
        assert rule.matches(policy, subject=subject, testcase='other_test_case')
        decision = Decision('bodhi_update_push_stable', 'rhel-9000')
        decision.check(subject, policies, results_retriever=None)
        assert len(decision.answers) == 2
        assert decision.answers[1].test_case_name == 'invalid-gating-yaml'

        # Reload rules to clear cache.
        policies = Policy.safe_load_all(policy_yaml)
        mock_retrieve_scm_from_koji.side_effect = NotFound
        assert rule.matches(policy, subject=subject, testcase='other_test_case')
        decision = Decision('bodhi_update_push_stable', 'rhel-9000')
        decision.check(subject, policies, results_retriever=None)
        assert [x.to_json()['type'] for x in decision.answers] == ['failed-fetch-gating-yaml']
        assert decision.answers[0].error == f'Koji build not found for {subject}'


@mock.patch('greenwave.resources.retrieve_scm_from_koji')
def test_remote_rule_exclude_no_source(mock_retrieve_scm_from_koji):
    policy_yaml = dedent("""
        --- !Policy
        id: "some_policy"
        product_versions: [rhel-9000]
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """)
    nvr = 'nethack-1.2.3-1.el9000'

    app = create_app('greenwave.config.TestingConfig')
    with app.app_context():
        subject = create_subject('koji_build', nvr)
        policies = Policy.safe_load_all(policy_yaml)
        assert len(policies) == 1

        policy = policies[0]
        assert len(policy.rules) == 1

        rule = policy.rules[0]

        mock_retrieve_scm_from_koji.side_effect = NoSourceException
        assert rule.matches(policy, subject=subject)
        assert rule.matches(policy, subject=subject, testcase='some_test_case')
        assert rule.matches(policy, subject=subject, testcase='other_test_case')

        decision = Decision('bodhi_update_push_stable', 'rhel-9000')
        decision.check(subject, policies, results_retriever=None)
        assert decision.answers == []


@pytest.mark.parametrize(('required_flag', 'required_value'), (
    ('true', True),
    ('True', True),
    ('on', True),
    ('On', True),
    ('ON', True),
    ('yes', True),
    ('Yes', True),
    ('YES', True),

    ('false', False),
    ('False', False),
    ('off', False),
    ('Off', False),
    ('OFF', False),
    ('no', False),
    ('No', False),
    ('NO', False),
))
def test_remote_rule_requiered_flag(required_flag, required_value):
    policy_yaml = dedent("""
        --- !Policy
        id: test
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: koji_build
        rules:
          - !RemoteRule {required: %s}
    """) % required_flag
    policies = Policy.safe_load_all(policy_yaml)
    assert len(policies) == 1
    assert len(policies[0].rules) == 1
    assert isinstance(policies[0].rules[0], RemoteRule)
    assert policies[0].rules[0].required == required_value


@pytest.mark.parametrize('required_flag', (
    '', '0', '1', 'nope', 'TRUe', 'oN'
))
def test_remote_rule_requiered_flag_bad(required_flag):
    policy_yaml = dedent("""
        --- !Policy
        id: test
        product_versions: [fedora-rawhide]
        decision_context: test
        subject_type: koji_build
        rules:
          - !RemoteRule {required: %s}
    """) % required_flag
    error = 'Expected a boolean value, got: {}'.format(required_flag)
    with pytest.raises(SafeYAMLError, match=error):
        Policy.safe_load_all(policy_yaml)
