# SPDX-License-Identifier: GPL-2.0+

from fnmatch import fnmatch
import glob
import logging
import os
import re
import greenwave.resources
from werkzeug.exceptions import BadRequest, NotFound
from flask import current_app
from greenwave.utils import remove_duplicates, to_hashable
from greenwave.safe_yaml import (
    SafeYAMLBool,
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

    def __hash__(self):
        return hash(to_hashable(self.to_json()))

    def __eq__(self, other):
        try:
            json1 = self.to_json()
            json2 = other.to_json()
        except NotImplementedError:
            return id(self) == id(other)
        return json1 == json2


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

    def to_waived(self):
        """
        Transform unsatisfied answer to waived one.
        """
        raise NotImplementedError()


class TestResultMissing(RuleNotSatisfied):
    """
    A required test case is missing (that is, we did not find any result in
    ResultsDB with a matching item and test case name).
    """

    def __init__(self, subject, test_case_name, scenario):
        self.subject = subject
        self.test_case_name = test_case_name
        self.scenario = scenario

    def to_json(self):
        return {
            'type': 'test-result-missing',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'scenario': self.scenario,
            # For backwards compatibility only:
            'item': self.subject.to_dict()
        }

    def to_waived(self):
        return TestResultWaived(self)


class TestResultWaived(RuleSatisfied):
    """
    A waived unsatisfied rule.

    Contains same data as unsatisfied rule except the type has "-waived"
    suffix. Also, the deprecated "item" field is dropped.
    """
    def __init__(self, unsatisfied_rule):
        self.unsatisfied_rule = unsatisfied_rule

    def to_json(self):
        satisfied_rule = self.unsatisfied_rule.to_json()
        satisfied_rule['type'] += '-waived'

        item = satisfied_rule.get('item')
        if isinstance(item, dict) and 'item' in item and 'type' in item:
            if 'subject_identifier' not in satisfied_rule:
                satisfied_rule['subject_identifier'] = item['item']
            if 'subject_type' not in satisfied_rule:
                satisfied_rule['subject_type'] = item['type']
            del satisfied_rule['item']

        return satisfied_rule


class TestResultFailed(RuleNotSatisfied):
    """
    A required test case did not pass (that is, its outcome in ResultsDB was
    not ``PASSED`` or ``INFO``).
    """

    def __init__(self, subject, test_case_name, scenario, result_id):
        self.subject = subject
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
            'item': self.subject.to_dict(),
            'scenario': self.scenario,
        }

    def to_waived(self):
        return TestResultWaived(self)


class TestResultErrored(RuleNotSatisfied):
    """
    A required test case failed to finish, i.e. the system failed during the
    testing process and could not finish the testing.  (outcome in ResultsDB
    was ``ERROR``).
    """

    def __init__(
            self,
            subject,
            test_case_name,
            scenario,
            result_id,
            error_reason):
        self.subject = subject
        self.test_case_name = test_case_name
        self.scenario = scenario
        self.result_id = result_id
        self.error_reason = error_reason

    def to_json(self):
        return {
            'type': 'test-result-errored',
            'testcase': self.test_case_name,
            'result_id': self.result_id,
            'error_reason': self.error_reason,
            # These are for backwards compatibility only
            # (the values are already visible in the result data itself, the
            # caller shouldn't need them repeated here):
            'item': self.subject.to_dict(),
            'scenario': self.scenario,
        }

    def to_waived(self):
        return TestResultWaived(self)


class InvalidRemoteRuleYaml(RuleNotSatisfied):
    """
    Remote policy parsing failed.
    """

    def __init__(self, subject, test_case_name, details):
        self.subject = subject
        self.test_case_name = test_case_name
        self.details = details

    def to_json(self):
        return {
            'type': 'invalid-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'details': self.details
        }

    def to_waived(self):
        return None


class MissingRemoteRuleYaml(RuleNotSatisfied):
    """
    Remote policy not found in remote repository.
    """

    test_case_name = 'missing-gating-yaml'

    def __init__(self, subject):
        self.subject = subject

    def to_json(self):
        return {
            'type': 'missing-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
        }

    def to_waived(self):
        return None


class TestResultPassed(RuleSatisfied):
    """
    A required test case passed (that is, its outcome in ResultsDB was
    ``PASSED`` or ``INFO``) or a corresponding waiver was found.
    """
    def __init__(self, subject, test_case_name, result_id):
        self.subject = subject
        self.test_case_name = test_case_name
        self.result_id = result_id

    def to_json(self):
        return {
            'type': 'test-result-passed',
            'testcase': self.test_case_name,
            'result_id': self.result_id,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
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


def _summarize_answers_without_errored(answers):
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

    summary = _summarize_answers_without_errored(answers)

    errored_count = len([answer for answer in answers if isinstance(answer, TestResultErrored)])
    if errored_count:
        summary += f' ({errored_count} {"error" if errored_count == 1 else "errors"})'

    return summary


class Rule(SafeYAMLObject):
    """
    An individual rule within a policy. A policy consists of multiple rules.
    When the policy is evaluated, each rule returns an answer
    (instance of :py:class:`Answer`).

    This base class is not used directly.
    """
    def check(
            self,
            policy,
            product_version,
            subject,
            results_retriever):
        """
        Evaluate this policy rule for the given item.

        Args:
            policy (Policy): Parent policy of the rule
            product_version (str): Product version we are making a decision about
            subject (Subject): Item we are making a decision about (for
                example, Koji build NVR, Bodhi update id, ...)
            results_retriever (ResultsRetriever): Object for retrieving data
                from ResultsDB.

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

    @staticmethod
    def process_on_demand_rules(rules):
        #pylint: disable=attribute-defined-outside-init
        """
        Validates rules and creates objects for them.

        Args:
            rules (json): User specified rules

        Returns:
            list: Returns a list of appropriate objects
        """
        if not all([rule.get('type') for rule in rules]):
            raise BadRequest('Key \'type\' is required for every rule')
        if not all([rule.get('test_case_name') for rule in rules if rule['type'] != 'RemoteRule']):
            raise BadRequest('Key \'test_case_name\' is required if not a RemoteRule')

        processed_rules = []
        for rule in rules:
            if rule['type'] == 'RemoteRule':
                temp_rule = RemoteRule()
                temp_rule.required = rule.get('required', False)
                processed_rules.append(temp_rule)
            elif rule['type'] == 'PassingTestCaseRule':
                temp_rule = PassingTestCaseRule()
                temp_rule.test_case_name = rule['test_case_name']
                temp_rule.scenario = rule.get('scenario')
                processed_rules.append(temp_rule)
            else:
                raise BadRequest('Invalid rule type {}'.format(rule['type']))

        return processed_rules


class RemoteRule(Rule):
    yaml_tag = '!RemoteRule'
    safe_yaml_attributes = {
        'required': SafeYAMLBool(optional=True, default=False),
    }

    @staticmethod
    def _get_sub_policies(policy, subject):
        if not subject.supports_remote_rule:
            return []

        rr_policies_conf = current_app.config.get('REMOTE_RULE_POLICIES', {})
        cur_subject_url = (
            rr_policies_conf.get(policy.subject_type) or
            rr_policies_conf.get('*') or
            current_app.config.get('DIST_GIT_URL_TEMPLATE')
        )

        if not cur_subject_url:
            raise RuntimeError(f'Cannot use a remote rule for {subject} subject '
                               f'as it has not been configured')

        response = None
        url_params = {}
        if '{pkg_name}' in cur_subject_url or '{pkg_namespace}' in cur_subject_url or \
                '{rev}' in cur_subject_url:
            try:
                pkg_namespace, pkg_name, rev = greenwave.resources.retrieve_scm_from_koji(
                    subject.identifier
                )
            except greenwave.resources.NoSourceException as e:
                log.error(e)
                return None

            # if the element is actually a container and not a pkg there will be a "-container"
            # string at the end of the "pkg_name" and it will not match with the one in the
            # remote rule file URL
            if pkg_namespace == 'containers':
                pkg_name = re.sub('-container$', '', pkg_name)
            if pkg_namespace:
                pkg_namespace += '/'
            url_params.update(rev=rev, pkg_name=pkg_name, pkg_namespace=pkg_namespace)

        if '{subject_id}' in cur_subject_url:
            subj_id = subject.identifier
            if subj_id.startswith('sha256:'):
                subj_id = subj_id[7:]
            url_params.update(subject_id=subj_id)

        response = greenwave.resources.retrieve_yaml_remote_rule(
            cur_subject_url.format(**url_params)
        )

        if response is None:
            # greenwave extension file not found
            return None

        policies = RemotePolicy.safe_load_all(response)
        if isinstance(policy, OnDemandPolicy):
            return [
                sub_policy for sub_policy in policies
                if any(sub_policy.matches_product_version(pv) for pv in policy.product_versions)
            ]

        return [
            sub_policy for sub_policy in policies
            if set(sub_policy.all_decision_contexts).intersection(policy.all_decision_contexts)
        ]

    @remove_duplicates
    def check(
            self,
            policy,
            product_version,
            subject,
            results_retriever):
        try:
            policies = self._get_sub_policies(policy, subject)
        except SafeYAMLError as e:
            return [
                InvalidRemoteRuleYaml(subject, 'invalid-gating-yaml', str(e))
            ]

        if policies is None:
            if self.required:
                return [MissingRemoteRuleYaml(subject)]
            return []

        answers = []
        for remote_policy in policies:
            if remote_policy.matches_product_version(product_version):
                response = remote_policy.check(
                    product_version, subject, results_retriever)

                if isinstance(response, list):
                    answers.extend(response)
                else:
                    answers.append(response)

        return answers

    def matches(self, policy, **attributes):
        #pylint: disable=broad-except
        subject = attributes.get('subject')
        if not subject:
            return True

        sub_policies = []
        try:
            sub_policies = self._get_sub_policies(policy, subject)
        except SafeYAMLError:
            logging.exception('Failed to parse policies for %r', subject)
        except NotFound:
            logging.error('Koji build not found for %r', subject)
        except Exception:
            logging.exception('Failed to retrieve policies for %r', subject)

        if sub_policies is None:
            # RemoteRule matches if remote policy file is missing.
            return True

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

    @remove_duplicates
    def check(
            self,
            policy,
            product_version,
            subject,
            results_retriever):
        matching_results = results_retriever.retrieve(subject, self.test_case_name)

        if self.scenario is not None:
            matching_results = [
                result for result in matching_results
                if self.scenario in result['data']['scenario']]

        # Investigate the absence of result first.
        if not matching_results:
            return TestResultMissing(subject, self.test_case_name, self.scenario)

        # If we find multiple matching results, we always use the first one which
        # will be the latest chronologically, because ResultsDB always returns
        # results ordered by `submit_time` descending.
        return [
            self._answer_for_result(result, subject)
            for result in matching_results
        ]

    def matches(self, policy, **attributes):
        testcase = attributes.get('testcase')
        return not testcase or testcase == self.test_case_name

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'scenario': self.scenario,
        }

    def _answer_for_result(self, result, subject):
        if result['outcome'] in ('PASSED', 'INFO'):
            log.debug('Test result passed for the result_id %s and testcase %s,'
                      ' because the outcome is %s', result['id'], self.test_case_name,
                      result['outcome'])
            return TestResultPassed(subject, self.test_case_name, result['id'])

        if result['outcome'] in ('QUEUED', 'RUNNING'):
            log.debug('Test result MISSING for the %s and '
                      'testcase %s, because the outcome is %s', subject,
                      self.test_case_name, result['outcome'])
            return TestResultMissing(subject, self.test_case_name, self.scenario)

        if result['outcome'] == 'ERROR':
            error_reason = result.get('error_reason')
            log.debug('Test result ERROR for the %s and '
                      'testcase %s, error reason: %s', subject,
                      self.test_case_name, error_reason)
            return TestResultErrored(
                subject, self.test_case_name, self.scenario, result['id'],
                error_reason)

        log.debug('Test result failed for the %s and '
                  'testcase %s, because the outcome is %s and it didn\'t match any of the '
                  'previous cases', subject, self.test_case_name, result['outcome'])
        return TestResultFailed(subject, self.test_case_name, self.scenario, result['id'])


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

    def check(
            self,
            policy,
            product_version,
            subject,
            results_retriever):
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
        'decision_contexts': SafeYAMLList(str, optional=True, default=list()),
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
        if decision_context and (decision_context not in self.all_decision_contexts):
            return False

        product_version = attributes.get('product_version')
        if product_version and not self.matches_product_version(product_version):
            return False

        if not self.matches_subject_type(**attributes):
            return False

        return not self.rules or any(rule.matches(self, **attributes) for rule in self.rules)

    def matches_subject_type(self, **attributes):
        subject = attributes.get('subject')
        return not subject or subject.type == self.subject_type

    @remove_duplicates
    def check(
            self,
            product_version,
            subject,
            results_retriever):
        # If an item is about a package and it is in the blacklist, return RuleSatisfied()
        name = subject.package_name
        if name:
            if name in self.blacklist:
                return [BlacklistedInPolicy(subject.identifier) for rule in self.rules]
            for exclude in self.excluded_packages:
                if fnmatch(name, exclude):
                    return [ExcludedInPolicy(subject.identifier) for rule in self.rules]
            if self.packages and not any(fnmatch(name, package) for package in self.packages):
                # If the `packages` whitelist is set and this package isn't in the
                # `packages` whitelist, then the policy doesn't apply to it
                return []
        answers = []
        for rule in self.rules:
            response = rule.check(
                self,
                product_version,
                subject,
                results_retriever)
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

    @property
    def all_decision_contexts(self):
        rv = []
        if self.decision_contexts:
            rv.extend(self.decision_contexts)
        if self.decision_context and self.decision_context not in rv:
            rv.append(self.decision_context)
        return rv


class OnDemandPolicy(Policy):
    root_yaml_tag = None

    @classmethod
    def create_from_json(cls, data):
        try:
            data2 = {
                'id': 'on-demand-policy',
                'product_versions': [data['product_version']],
                'decision_context': 'on-demand-policy',
                'subject_type': 'unused',
            }
            data2.update(data)
            result = cls.from_value(data2)
            return result
        except SafeYAMLError as e:
            raise BadRequest('Failed to parse on demand policy: {}'.format(e))

    def matches_subject_type(self, **attributes):
        return True


class RemotePolicy(Policy):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(optional=True),
        'product_versions': SafeYAMLList(str, default=['*'], optional=True),
        'subject_type': SafeYAMLString(optional=True, default='koji_build'),
        'decision_context': SafeYAMLString(),
        'decision_contexts': SafeYAMLList(str, optional=True),
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
            for decision_context in policy.all_decision_contexts:
                yield decision_context, product_version
    else:
        for policy in applicable_policies:
            # FIXME: This can returns product version patterns like 'fedora-*'.
            for product_version in policy.product_versions:
                for decision_context in policy.all_decision_contexts:
                    yield decision_context, product_version


def applicable_decision_context_product_version_pairs(policies, **attributes):
    contexts_product_versions = sorted(set(
        _applicable_decision_context_product_version_pairs(
            policies, **attributes)))

    log.debug("found %i decision contexts", len(contexts_product_versions))
    return contexts_product_versions


def _missing_decision_contexts_in_parent_policies(policies):
    missing_decision_contexts = set()
    for policy in policies:
        # Assume a parent policy is not present for a policy in the remote rule
        for parent_policy in current_app.config['policies']:
            missing_decision_contexts.update(
                set(parent_policy.all_decision_contexts).difference(policy.all_decision_contexts)
            )
    return list(missing_decision_contexts)
