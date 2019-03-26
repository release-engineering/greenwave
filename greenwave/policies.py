# SPDX-License-Identifier: GPL-2.0+

from fnmatch import fnmatch
import glob
import logging
import os
import re
import greenwave.resources
from flask import current_app

from greenwave.safe_yaml import (
    SafeYAMLChoice,
    SafeYAMLList,
    SafeYAMLObject,
    SafeYAMLString,
    SafeYAMLError,
)

log = logging.getLogger(__name__)


def load_policies(policies_dir):
    """
    Load Greenwave policies from the given policies directory.

    :param str policies_dir: A path points to the policies directory.
    :return: A list of policies.

    """
    policy_pathnames = glob.glob(os.path.join(policies_dir, '*.yaml'))
    policies = []
    for policy_pathname in policy_pathnames:
        with open(policy_pathname, 'r') as f:
            policies.extend(greenwave.policies.Policy.safe_load_all(f))
    log.debug("Loaded %i policies from %s", len(policies), policies_dir)
    return policies


class DisallowedRuleError(RuntimeError):
    pass


def subject_type_identifier_to_item(subject_type, subject_identifier):
    """
    Greenwave < 0.8 included an "item" key in the "unsatisfied_requirements".
    This returns a suitable value for that key, for backwards compatibility.
    """
    if subject_type == 'compose':
        return {'productmd.compose.id': subject_identifier}
    else:
        return {'type': subject_type, 'item': subject_identifier}


class Answer(object):
    """
    Represents the result of evaluating a policy rule against a particular
    item. But we call it an "answer" because the word "result" is a bit
    overloaded in here. :-)

    This base class is not used directly -- each answer is an instance of
    a subclass, depending on what the answer was.
    """

    def to_json(self):
        """
        Returns a machine-readable description of the problem for API responses.
        """
        raise NotImplementedError()


class RuleSatisfied(Answer):
    """
    The rule's requirements are satisfied for this item.
    """

    is_satisfied = True

    def to_json(self):
        raise NotImplementedError()


class RuleNotSatisfied(Answer):
    """
    The rule's requirements are not satisfied for this item.

    Not used directly -- the answer is an instance of a subclass, specifying
    exactly what was not satisfied.
    """

    is_satisfied = False

    def to_json(self):
        raise NotImplementedError()


class TestResultMissing(RuleNotSatisfied):
    """
    A required test case is missing (that is, we did not find any result in
    ResultsDB with a matching item and test case name).
    """

    def __init__(self, subject_type, subject_identifier, test_case_name, scenario):
        self.subject_type = subject_type
        self.subject_identifier = subject_identifier
        self.test_case_name = test_case_name
        self.scenario = scenario

    def to_json(self):
        return {
            'type': 'test-result-missing',
            'testcase': self.test_case_name,
            'subject_type': self.subject_type,
            'subject_identifier': self.subject_identifier,
            'scenario': self.scenario,
            # For backwards compatibility only:
            'item': subject_type_identifier_to_item(self.subject_type, self.subject_identifier),
        }


class TestResultMissingWaived(RuleSatisfied):
    """
    Same as TestResultMissing but the result was waived.
    """
    def __init__(self, subject_type, subject_identifier, test_case_name, scenario):
        self.subject_type = subject_type
        self.subject_identifier = subject_identifier
        self.test_case_name = test_case_name
        self.scenario = scenario

    def to_json(self):
        return {
            'type': 'test-result-missing-waived',
            'testcase': self.test_case_name,
            'subject_type': self.subject_type,
            'subject_identifier': self.subject_identifier,
            'scenario': self.scenario,
        }


class TestResultFailed(RuleNotSatisfied):
    """
    A required test case did not pass (that is, its outcome in ResultsDB was
    not ``PASSED`` or ``INFO``) and no corresponding waiver was found.
    """

    def __init__(self, subject_type, subject_identifier, test_case_name, scenario, result_id):
        self.subject_type = subject_type
        self.subject_identifier = subject_identifier
        self.test_case_name = test_case_name
        self.scenario = scenario
        self.result_id = result_id

    def to_json(self):
        return {
            'type': 'test-result-failed',
            'testcase': self.test_case_name,
            'result_id': self.result_id,
            # These are for backwards compatibility only
            # (the values are already visible in the result data itself, the
            # caller shouldn't need them repeated here):
            'item': subject_type_identifier_to_item(self.subject_type, self.subject_identifier),
            'scenario': self.scenario,
        }


class InvalidGatingYaml(RuleNotSatisfied):
    """
    Remote policy parsing failed.
    """

    def __init__(self, subject_type, subject_identifier, test_case_name, details):
        self.subject_type = subject_type
        self.subject_identifier = subject_identifier
        self.test_case_name = test_case_name
        self.details = details

    def to_json(self):
        return {
            'type': 'invalid-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject_type,
            'subject_identifier': self.subject_identifier,
            'details': self.details
        }


class TestResultPassed(RuleSatisfied):
    """
    A required test case passed (that is, its outcome in ResultsDB was
    ``PASSED`` or ``INFO``) or a corresponding waiver was found.
    """
    def __init__(self, test_case_name, result_id):
        self.test_case_name = test_case_name
        self.result_id = result_id

    def to_json(self):
        return {
            'type': 'test-result-passed',
            'testcase': self.test_case_name,
            'result_id': self.result_id,
        }


class BlacklistedInPolicy(RuleSatisfied):
    """
    Package was blacklisted in policy.
    """
    def __init__(self, subject_identifier):
        self.subject_identifier = subject_identifier

    def to_json(self):
        return {
            'type': 'blacklisted',
            'subject_identifier': self.subject_identifier,
        }


class ExcludedInPolicy(RuleSatisfied):
    """
    Package was excluded in policy.
    """
    def __init__(self, subject_identifier):
        self.subject_identifier = subject_identifier

    def to_json(self):
        return {
            'type': 'excluded',
            'subject_identifier': self.subject_identifier,
        }


def summarize_answers(answers):
    """
    Produces a one-sentence human-readable summary of the result of evaluating a policy.

    Args:
        answers (list): List of :py:class:`Answers <Answer>` from evaluating a policy.

    Returns:
        str: Human-readable summary.
    """
    if not answers:
        return 'no tests are required'

    failure_count = len([answer for answer in answers if isinstance(answer, RuleNotSatisfied)])
    missing_count = len([answer for answer in answers if isinstance(answer, TestResultMissing)])

    # Missing results are also failures but we will distinguish between those
    # two in summary message.
    failure_count -= missing_count

    if failure_count and missing_count:
        return '{} of {} required tests failed, {} result{} missing'.format(
            failure_count, len(answers), missing_count, 's' if missing_count > 1 else '')

    if failure_count > 0:
        return '{} of {} required tests failed'.format(failure_count, len(answers))

    if missing_count > 0:
        return '{} of {} required test results missing'.format(missing_count, len(answers))

    if all(answer.is_satisfied for answer in answers):
        return 'All required tests passed'

    assert False, 'Unexpected unsatisfied result'
    return 'inexplicable result'


class Rule(SafeYAMLObject):
    """
    An individual rule within a policy. A policy consists of multiple rules.
    When the policy is evaluated, each rule returns an answer
    (instance of :py:class:`Answer`).

    This base class is not used directly.
    """
    def check(self, policy, product_version, subject_identifier, results_retriever, waivers):
        """
        Evaluate this policy rule for the given item.

        Args:
            policy (Policy): Parent policy of the rule
            product_version (str): Product version we are making a decision about
            subject_identifier (str): Item we are making a decision about (for
                example, Koji build NVR, Bodhi update id, ...)
            results_retriever (ResultsRetriever): Object for retrieving data
                from ResultsDB.
            waivers (list): List of waiver objects looked up in WaiverDB for the results.

        Returns:
            Answer: An instance of a subclass of :py:class:`Answer` describing the result.
        """
        raise NotImplementedError()

    def matches(self, policy, **attributes):
        #pylint: disable=unused-argument
        """
        Same as Policy.matches() for a rule attributes.

        Args:
            policy (Policy): Parent policy of the rule

        Returns:
            bool: True only if provided attributes matches the rule
        """
        return True


def waives_invalid_gating_yaml(waiver, subject_type, subject_identifier):
    return (waiver['testcase'] == 'invalid-gating-yaml' and
            waiver['subject']['type'] == subject_type and
            waiver['subject']['item'] == subject_identifier)


class RemoteRule(Rule):
    yaml_tag = '!RemoteRule'
    safe_yaml_attributes = {}

    def _get_sub_policies(self, policy, subject_identifier):
        if policy.subject_type not in ['koji_build', 'redhat-module']:
            return []

        pkg_namespace, pkg_name, rev = greenwave.resources.retrieve_scm_from_koji(
            subject_identifier)
        # if the element is actually a container and not a pkg there will be a "-container"
        # string at the end of the "pkg_name" and it will not match with the one in the
        # gating.yaml URL
        if pkg_namespace == 'containers':
            pkg_name = re.sub('-container$', '', pkg_name)
        response = greenwave.resources.retrieve_yaml_remote_rule(rev, pkg_name, pkg_namespace)

        if response is None:
            # greenwave extension file not found
            return []

        policies = RemotePolicy.safe_load_all(response)
        return [
            sub_policy for sub_policy in policies
            if sub_policy.decision_context == policy.decision_context
        ]

    def check(self, policy, product_version, subject_identifier, results_retriever, waivers):

        try:
            policies = self._get_sub_policies(policy, subject_identifier)
        except SafeYAMLError as e:
            if any(waives_invalid_gating_yaml(waiver, policy.subject_type, subject_identifier)
                    for waiver in waivers):
                return []
            return [
                InvalidGatingYaml(
                    policy.subject_type, subject_identifier, 'invalid-gating-yaml', str(e))
            ]

        answers = []
        for remote_policy in policies:
            if remote_policy.matches_product_version(product_version):
                response = remote_policy.check(
                    product_version, subject_identifier, results_retriever, waivers)

                if isinstance(response, list):
                    answers.extend(response)
                else:
                    answers.append(response)

        return answers

    def matches(self, policy, **attributes):
        #pylint: disable=broad-except
        subject_identifier = attributes.get('subject_identifier')
        if not subject_identifier:
            return True

        sub_policies = []
        try:
            sub_policies = self._get_sub_policies(policy, subject_identifier)
        except SafeYAMLError:
            logging.exception(
                'Failed to parse policies for %r', subject_identifier)
        except Exception:
            logging.exception(
                'Failed to retrieve policies for %r', subject_identifier)

        return any(sub_policy.matches(**attributes) for sub_policy in sub_policies)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
        }


class PassingTestCaseRule(Rule):
    """
    This rule requires either a passing result for the given test case, or
    a non-passing result with a waiver.
    """
    yaml_tag = '!PassingTestCaseRule'

    safe_yaml_attributes = {
        'test_case_name': SafeYAMLString(),
        'scenario': SafeYAMLString(optional=True),
    }

    def check(self, policy, product_version, subject_identifier, results_retriever, waivers):
        matching_results = results_retriever.retrieve(
            policy.subject_type, subject_identifier, self.test_case_name)
        matching_waivers = [
            w for w in waivers if (w['testcase'] == self.test_case_name and w['waived'] is True)]

        if self.scenario is not None:
            matching_results = [
                result for result in matching_results
                if self.scenario in result['data']['scenario']]

        # Investigate the absence of result first.
        if not matching_results:
            if not matching_waivers:
                return TestResultMissing(
                    policy.subject_type, subject_identifier, self.test_case_name, self.scenario)
            return TestResultMissingWaived(
                policy.subject_type, subject_identifier, self.test_case_name, self.scenario)

        # For compose make decisions based on all architectures and variants.
        if policy.subject_type == 'compose':
            visited_arch_variants = set()
            answers = []
            for result in matching_results:
                result_data = result['data']

                # Items under test result "data" are lists which are unhashable
                # types in Python. This converts anything that is stored there
                # to a string so we don't have to care about the stored value.
                arch_variant = (
                    str(result_data.get('system_architecture')),
                    str(result_data.get('system_variant')))

                if arch_variant not in visited_arch_variants:
                    visited_arch_variants.add(arch_variant)
                    answer = self._answer_for_result(
                        result, waivers, policy.subject_type, subject_identifier)
                    answers.append(answer)

            return answers

        # If we find multiple matching results, we always use the first one which
        # will be the latest chronologically, because ResultsDB always returns
        # results ordered by `submit_time` descending.
        answers = []
        for result in matching_results:
            answers.append(self._answer_for_result(
                result, waivers, policy.subject_type, subject_identifier))
        return answers

    def matches(self, policy, **attributes):
        testcase = attributes.get('testcase')
        return not testcase or testcase == self.test_case_name

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'scenario': self.scenario,
        }

    def _answer_for_result(self, result, waivers, subject_type, subject_identifier):
        if result['outcome'] in ('PASSED', 'INFO'):
            log.debug('Test result passed for the result_id %s and testcase %s,'
                      ' because the outcome is %s', result['id'], self.test_case_name,
                      result['outcome'])
            return TestResultPassed(self.test_case_name, result['id'])

        # TODO limit who is allowed to waive

        matching_waivers = [w for w in waivers if (
            w['subject_type'] == subject_type and
            w['subject_identifier'] == result['data']['item'][0] and
            w['testcase'] == result['testcase']['name'] and
            w['waived'] is True
        )]
        if matching_waivers:
            log.debug('Found matching waivers for the result_id %s and the testcase %s,'
                      ' so the Test result is PASSED', result['id'], self.test_case_name)
            return TestResultPassed(self.test_case_name, result['id'])
        if result['outcome'] in ('QUEUED', 'RUNNING'):
            log.debug('Test result MISSING for the subject_type %s, subject_identifier %s and '
                      'testcase %s, because the outcome is %s', subject_type, subject_identifier,
                      self.test_case_name, result['outcome'])
            return TestResultMissing(subject_type, subject_identifier, self.test_case_name,
                                     self.scenario)
        log.debug('Test result failed for the subject_type %s, subject_identifier %s and '
                  'testcase %s, because the outcome is %s and it didn\'t match any of the '
                  'previous cases', subject_type, subject_identifier,
                  self.test_case_name, result['outcome'])
        return TestResultFailed(subject_type, subject_identifier, self.test_case_name,
                                self.scenario, result['id'])


class ObsoleteRule(Rule):
    """
    The base class for an obsolete rule.
    When these rules are parsed, a SafeYAMLError exception will be raised.
    """
    advice = 'Please refer to the documentation for more information.'
    safe_yaml_attributes = {}

    def __init__(self):
        tag = self.yaml_tag or '!' + type(self).__name__
        raise SafeYAMLError('{} is obsolete. {}'.format(tag, self.advice))

    def check(self, policy, product_version, subject_identifier, results_retriever, waivers):
        raise ValueError('This rule is obsolete and can\'t be checked')


class PackageSpecificBuild(ObsoleteRule):
    yaml_tag = '!PackageSpecificBuild'
    advice = 'Please use the "packages" whitelist instead.'


class FedoraAtomicCi(PackageSpecificBuild):
    yaml_tag = '!FedoraAtomicCi'


class Policy(SafeYAMLObject):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(),
        'product_versions': SafeYAMLList(str),
        'decision_context': SafeYAMLString(),
        # TODO: Handle brew-build value better.
        'subject_type': SafeYAMLString(),
        'rules': SafeYAMLList(Rule),
        'blacklist': SafeYAMLList(str, optional=True),
        'excluded_packages': SafeYAMLList(str, optional=True),
        'packages': SafeYAMLList(str, optional=True),
        'relevance_key': SafeYAMLString(optional=True),
        'relevance_value': SafeYAMLString(optional=True),
    }

    def matches(self, **attributes):
        """
        Returns True only if policy matches provided attributes.

        If an attribute to match is missing it's treated as irrelevant, i.e."match anything".

        Unknown attributes are ignored.

        There must be at least one matching rule or no rules in the policy.
        """
        decision_context = attributes.get('decision_context')
        if decision_context and decision_context != self.decision_context:
            return False

        product_version = attributes.get('product_version')
        if product_version and not self.matches_product_version(product_version):
            return False

        subject_type = attributes.get('subject_type')
        if subject_type and subject_type != self.subject_type:
            return False

        return not self.rules or any(rule.matches(self, **attributes) for rule in self.rules)

    def check(self, product_version, subject_identifier, results_retriever, waivers):
        # If an item is about a package and it is in the blacklist, return RuleSatisfied()
        if self.subject_type == 'koji_build':
            name = subject_identifier.rsplit('-', 2)[0]
            if name in self.blacklist:
                return [BlacklistedInPolicy(subject_identifier) for rule in self.rules]
            for exclude in self.excluded_packages:
                if fnmatch(name, exclude):
                    return [ExcludedInPolicy(subject_identifier) for rule in self.rules]
            if self.packages and not any(fnmatch(name, package) for package in self.packages):
                # If the `packages` whitelist is set and this package isn't in the
                # `packages` whitelist, then the policy doesn't apply to it
                return []
        answers = []
        for rule in self.rules:
            response = rule.check(
                self, product_version, subject_identifier, results_retriever, waivers)
            if isinstance(response, list):
                answers.extend(response)
            else:
                answers.append(response)
        return answers

    def matches_product_version(self, product_version):
        return any(fnmatch(product_version, version) for version in self.product_versions)

    @property
    def safe_yaml_label(self):
        return 'Policy {!r}'.format(self.id or 'untitled')


class RemotePolicy(Policy):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(optional=True),
        'product_versions': SafeYAMLList(str),
        'subject_type': SafeYAMLChoice('koji_build', 'redhat-module', optional=True),
        'decision_context': SafeYAMLString(),
        'rules': SafeYAMLList(Rule),
        'blacklist': SafeYAMLList(str, optional=True),
        'excluded_packages': SafeYAMLList(str, optional=True),
        'packages': SafeYAMLList(str, optional=True),
    }

    def validate(self):
        for rule in self.rules:
            if isinstance(rule, RemoteRule):
                raise SafeYAMLError('RemoteRule is not allowed in remote policies')
        super().validate()


def _applicable_decision_context_product_version_pairs(policies, **attributes):
    applicable_policies = [
        policy for policy in policies if policy.matches(**attributes)
    ]

    log.debug("found %i applicable policies of %i for: %r",
              len(applicable_policies), len(policies), attributes)

    product_version = attributes.get('product_version')
    if product_version:
        for policy in applicable_policies:
            yield policy.decision_context, product_version
    else:
        for policy in applicable_policies:
            # FIXME: This can returns product version patterns like 'fedora-*'.
            for product_version in policy.product_versions:
                yield policy.decision_context, product_version


def applicable_decision_context_product_version_pairs(policies, **attributes):
    contexts_product_versions = sorted(set(
        _applicable_decision_context_product_version_pairs(
            policies, **attributes)))

    log.debug("found %i decision contexts", len(contexts_product_versions))
    return contexts_product_versions


def _missing_decision_contexts_in_parent_policies(policies):
    missing_decision_contexts = []
    for policy in policies:
        # Assume a parent policy is not present for a policy in the remote rule
        parent_present = False
        for parent_policy in current_app.config['policies']:
            if parent_policy.decision_context == policy.decision_context:
                parent_present = True
                break
        # If there are no parent policies for a decision_context in the remote rule,
        # report it as missing to warn the user.
        if not parent_present:
            missing_decision_contexts.append(policy.decision_context)
    return missing_decision_contexts
