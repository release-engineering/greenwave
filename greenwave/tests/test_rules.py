import mock

from textwrap import dedent

from greenwave.app_factory import create_app
from greenwave.policies import Policy
from greenwave.safe_yaml import SafeYAMLError


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


def test_match_package_specific_rule():
    policy_yaml = dedent("""
        --- !Policy
        id: "some_policy"
        product_versions: [rhel-9000]
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !PackageSpecificBuild {test_case_name: some_test_case, repos: [nethack]}
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
        policies = Policy.safe_load_all(policy_yaml)
        assert len(policies) == 1

        policy = policies[0]
        assert len(policy.rules) == 1

        rule = policy.rules[0]
        assert rule.matches(policy)
        assert rule.matches(policy, subject_identifier=nvr)
        assert rule.matches(policy, subject_identifier=nvr, testcase='some_test_case')
        assert not rule.matches(policy, subject_identifier=nvr, testcase='other_test_case')

        # Simulate invalid gating.yaml file.
        def raiseYamlError(*args):
            raise SafeYAMLError()
        mock_retrieve_yaml_remote_rule.side_effect = raiseYamlError

        assert rule.matches(policy)
        assert not rule.matches(policy, subject_identifier=nvr)
        assert not rule.matches(policy, subject_identifier=nvr, testcase='some_test_case')
        assert not rule.matches(policy, subject_identifier=nvr, testcase='other_test_case')
