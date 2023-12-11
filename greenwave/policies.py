# SPDX-License-Identifier: GPL-2.0+

from fnmatch import fnmatch
import glob
import logging
import os
import re
from typing import Optional

from defusedxml.xmlrpc import xmlrpc_client
from werkzeug.exceptions import BadGateway, BadRequest, NotFound
from flask import current_app

import greenwave.resources
from greenwave.safe_yaml import (
    SafeYAMLBool,
    SafeYAMLDateTime,
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


def _remote_url_templates(subject):
    rr_policies_conf = current_app.config.get('REMOTE_RULE_POLICIES', {})
    cur_subject_urls = (
        rr_policies_conf.get(subject.type) or
        rr_policies_conf.get('*') or
        current_app.config.get('DIST_GIT_URL_TEMPLATE')
    )

    if not cur_subject_urls:
        raise RuntimeError(f'Cannot use a remote rule for {subject} subject '
                           f'as it has not been configured')

    if not isinstance(cur_subject_urls, list):
        cur_subject_urls = [cur_subject_urls]

    return cur_subject_urls


def _remote_urls(subject, url_templates):
    """
    Returns generator with possible remote rule URLs.
    """
    for current_url in url_templates:
        url_params = {}
        if '{pkg_name}' in current_url or '{pkg_namespace}' in current_url or \
                '{rev}' in current_url:
            try:
                pkg_namespace, pkg_name, rev = greenwave.resources.retrieve_scm_from_koji(
                    subject.identifier
                )
            except greenwave.resources.NoSourceException as e:
                log.warning(e)
                continue

            # if the element is actually a container and not a pkg there will be a "-container"
            # string at the end of the "pkg_name" and it will not match with the one in the
            # remote rule file URL
            if pkg_namespace == 'containers':
                pkg_name = re.sub('-container$', '', pkg_name)
            if pkg_namespace:
                pkg_namespace += '/'
            url_params.update(rev=rev, pkg_name=pkg_name, pkg_namespace=pkg_namespace)

        if '{subject_id}' in current_url:
            subj_id = subject.identifier
            if subj_id.startswith('sha256:'):
                subj_id = subj_id[7:]
            url_params.update(subject_id=subj_id)

        yield current_url.format(**url_params)


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

    is_test_result = True

    def to_json(self):
        """
        Returns a machine-readable description of the problem for API responses.
        """
        raise NotImplementedError()

    def __repr__(self):
        attributes = ' '.join(f'{k}={v}' for k, v in self.to_json().items())
        return f'<{self.__class__.__name__} {attributes}>'


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

    def to_waived(self, waiver_id):
        """
        Transform unsatisfied answer to waived one.
        """
        raise NotImplementedError()


class TestResultMissing(RuleNotSatisfied):
    """
    A required test case is missing (that is, we did not find any result in
    ResultsDB with a matching item and test case name).
    """

    def __init__(self, subject, test_case_name, scenario, source):
        self.subject = subject
        self.test_case_name = test_case_name
        self.scenario = scenario
        self.source = source

    def to_json(self):
        return {
            'type': 'test-result-missing',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'scenario': self.scenario,
            'source': self.source,

            # For backwards compatibility only:
            'item': self.subject.to_dict()
        }

    def to_waived(self, waiver_id):
        return TestResultWaived(self, waiver_id)


class TestResultIncomplete(RuleNotSatisfied):
    """
    A required test case is incomplete (that is, we did not find any completed
    result outcomes in ResultsDB with a matching item and test case name).
    """

    def __init__(self, subject, test_case_name, source, result_id, data):
        self.subject = subject
        self.test_case_name = test_case_name
        self.source = source
        self.result_id = result_id
        self.data = data

    @property
    def scenario(self):
        return self.data.get('scenario')

    def to_json(self):
        data = {
            # Same type as TestResultMissing for backwards compatibility
            'type': 'test-result-missing',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'source': self.source,
            'result_id': self.result_id,

            # For backwards compatibility only:
            'item': self.subject.to_dict()
        }
        data.update(self.data)
        return data

    def to_waived(self, waiver_id):
        return TestResultWaived(self, waiver_id)


class TestResultWaived(RuleSatisfied):
    """
    A waived unsatisfied rule.

    Contains same data as unsatisfied rule except the type has "-waived"
    suffix. Also, the deprecated "item" field is dropped.
    """
    def __init__(self, unsatisfied_rule, waiver_id):
        self.unsatisfied_rule = unsatisfied_rule
        self.waiver_id = waiver_id

    def to_json(self):
        satisfied_rule = self.unsatisfied_rule.to_json()
        satisfied_rule['type'] += '-waived'
        satisfied_rule['waiver_id'] = self.waiver_id

        if 'item' in satisfied_rule:
            del satisfied_rule['item']

        return satisfied_rule


class TestResultFailed(RuleNotSatisfied):
    """
    A required test case did not pass (that is, its outcome in ResultsDB was
    not passing).
    """

    def __init__(self, subject, test_case_name, source, result_id, data):
        self.subject = subject
        self.test_case_name = test_case_name
        self.source = source
        self.result_id = result_id
        self.data = data

    @property
    def scenario(self):
        return self.data.get('scenario')

    def to_json(self):
        data = {
            'type': 'test-result-failed',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'source': self.source,
            'result_id': self.result_id,

            # These are for backwards compatibility only
            # (the values are already visible in the result data itself, the
            # caller shouldn't need them repeated here):
            'item': self.subject.to_dict(),
        }
        data.update(self.data)
        return data

    def to_waived(self, waiver_id):
        return TestResultWaived(self, waiver_id)


class TestResultErrored(RuleNotSatisfied):
    """
    A required test case failed to finish, i.e. the system failed during the
    testing process and could not finish the testing (outcome in ResultsDB
    was an error).
    """

    def __init__(
            self,
            subject,
            test_case_name,
            source,
            result_id,
            data,
            error_reason):
        self.subject = subject
        self.test_case_name = test_case_name
        self.source = source
        self.result_id = result_id
        self.data = data
        self.error_reason = error_reason

    @property
    def scenario(self):
        return self.data.get('scenario')

    def to_json(self):
        data = {
            'type': 'test-result-errored',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'source': self.source,
            'result_id': self.result_id,
            'error_reason': self.error_reason,

            # These are for backwards compatibility only
            # (the values are already visible in the result data itself, the
            # caller shouldn't need them repeated here):
            'item': self.subject.to_dict(),
        }
        data.update(self.data)
        return data

    def to_waived(self, waiver_id):
        return TestResultWaived(self, waiver_id)


class InvalidRemoteRuleYaml(RuleNotSatisfied):
    """
    Remote policy parsing failed.
    """

    scenario = None

    def __init__(self, subject, test_case_name, details, source):
        self.subject = subject
        self.test_case_name = test_case_name
        self.details = details
        self.source = source

    def to_json(self):
        return {
            'type': 'invalid-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'scenario': self.scenario,
            'source': self.source,
            'details': self.details
        }

    def to_waived(self, waiver_id):
        return None


class MissingRemoteRuleYaml(RuleNotSatisfied):
    """
    Remote policy not found in remote repository.
    """

    test_case_name = 'missing-gating-yaml'
    scenario = None

    def __init__(self, subject, sources):
        self.subject = subject
        self.sources = sources

    def to_json(self):
        return {
            'type': 'missing-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'scenario': self.scenario,
            'sources': self.sources,
        }

    def to_waived(self, waiver_id):
        return None


class FailedFetchRemoteRuleYaml(RuleNotSatisfied):
    """
    Error while fetching remote policy.
    """

    scenario = None

    test_case_name = 'failed-fetch-gating-yaml'

    def __init__(self, subject, sources, error):
        self.subject = subject
        self.sources = sources
        self.error = error

    def to_json(self):
        return {
            'type': 'failed-fetch-gating-yaml',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'scenario': self.scenario,
            'sources': self.sources,
            'error': self.error,
        }

    def to_waived(self, waiver_id):
        return None


class FetchedRemoteRuleYaml(RuleSatisfied):
    """
    Remote policy was found in remote repository.
    """

    is_test_result = False

    def __init__(self, subject, source):
        self.subject = subject
        self.source = source

    def to_json(self):
        return {
            'type': 'fetched-gating-yaml',
            'testcase': 'fetched-gating-yaml',
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'source': self.source,
        }


class TestResultPassed(RuleSatisfied):
    """
    A required test case passed (that is, its outcome in ResultsDB was passing)
    or a corresponding waiver was found.
    """
    def __init__(self, subject, test_case_name, source, result_id, data):
        self.subject = subject
        self.test_case_name = test_case_name
        self.source = source
        self.result_id = result_id
        self.data = data

    def to_json(self):
        data = {
            'type': 'test-result-passed',
            'testcase': self.test_case_name,
            'subject_type': self.subject.type,
            'subject_identifier': self.subject.identifier,
            'source': self.source,
            'result_id': self.result_id,
        }
        data.update(self.data)
        return data


class ExcludedInPolicy(RuleSatisfied):
    """
    Package was excluded in policy.
    """
    def __init__(self, subject_identifier, policy):
        self.subject_identifier = subject_identifier
        self.policy = policy

    def to_json(self):
        return {
            'type': 'excluded',
            'subject_identifier': self.subject_identifier,
            'policy': self.policy.id,
            'source': self.policy.source,
        }


def _summarize_answers_without_errored(answers):
    failure_count = sum(
        1 for answer in answers
        if isinstance(answer, RuleNotSatisfied)
    )
    missing_count = sum(
        1 for answer in answers
        if isinstance(answer, (TestResultIncomplete, TestResultMissing))
    )

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

    logging.error('Unexpected unsatisfied result')
    return 'inexplicable result'


def summarize_answers(answers):
    """
    Produces a one-sentence human-readable summary of the result of evaluating a policy.

    Args:
        answers (list): List of :py:class:`Answers <Answer>` from evaluating a policy.

    Returns:
        str: Human-readable summary.
    """
    test_answers = [
        answer for answer in answers
        if answer.is_test_result
    ]
    if not test_answers:
        return 'no tests are required'

    summary = _summarize_answers_without_errored(test_answers)

    errored_count = len([
        answer for answer in test_answers
        if isinstance(answer, TestResultErrored)
    ])
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

    def check(self, policy, rule_context):
        """
        Evaluate this policy rule for the given item.

        Args:
            policy (Policy): Parent policy of the rule
            rule_context (RuleContext): rule context

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

    def __eq__(self, other):
        return self.to_json() == other.to_json()


class RemoteRule(Rule):
    yaml_tag = '!RemoteRule'
    safe_yaml_attributes = {
        'sources': SafeYAMLList(str, optional=True),
        'required': SafeYAMLBool(optional=True, default=False),
    }

    def _get_sub_policies(self, policy, subject):
        #pylint: disable=broad-except
        """
        Returns matching policies from the first available remote rule file,
        and answers (including FetchedRemoteRuleYaml, MissingRemoteRuleYaml,
        InvalidRemoteRuleYaml, FailedFetchRemoteRuleYaml).
        """
        if not subject.supports_remote_rule:
            return [], []

        remote_policies_urls = []
        remote_policies_url = None
        response = None
        answers = []

        try:
            url_templates = self.sources or _remote_url_templates(subject)
            for remote_policies_url in _remote_urls(subject, url_templates):
                remote_policies_urls.append(remote_policies_url)
                response = greenwave.resources.retrieve_yaml_remote_rule(remote_policies_url)
                if response is not None:
                    break
        except NotFound:
            error = f'Koji build not found for {subject}'
            return [], [FailedFetchRemoteRuleYaml(subject, remote_policies_urls, error)]
        except xmlrpc_client.Fault as err:
            logging.exception('Unexpected Koji XMLRPC fault with code: %s', err.faultCode)
            error = f'Koji XMLRPC fault due to: \'{err.faultString}\''
            raise BadGateway(error)
        except greenwave.resources.KojiScmUrlParseError as err:
            return [], [FailedFetchRemoteRuleYaml(subject, remote_policies_urls, err.description)]
        except Exception:
            logging.exception('Failed to retrieve policies for %r', subject)
            error = 'Unexpected error while fetching remote policies'
            raise BadGateway(error)

        # Remote rule file not found?
        if response is None:
            if self.required:
                answers.append(MissingRemoteRuleYaml(subject, remote_policies_urls))
            return [], answers

        answers.append(FetchedRemoteRuleYaml(subject, remote_policies_url))

        try:
            policies = RemotePolicy.safe_load_all(response)
        except SafeYAMLError as e:
            answers.append(
                InvalidRemoteRuleYaml(
                    subject, 'invalid-gating-yaml', str(e), remote_policies_url))
            policies = []

        for sub_policy in policies:
            sub_policy.source = remote_policies_url

        sub_policies = [
            sub_policy for sub_policy in policies
            if policy.matches_sub_policy(sub_policy)
        ]
        return sub_policies, answers

    def check(self, policy, rule_context):
        policies, answers = self._get_sub_policies(policy, rule_context.subject)

        # Copy cached value.
        answers = list(answers)

        for remote_policy in policies:
            if remote_policy.matches(
                decision_context=rule_context.decision_context,
                product_version=rule_context.product_version,
            ):
                response = remote_policy.check(rule_context)

                if not isinstance(response, list):
                    response = [response]

                answers.extend(response)

        return answers

    def matches(self, policy, **attributes):
        if attributes.get('match_any_remote_rule'):
            return True

        subject = attributes.get('subject')
        if not subject:
            return True

        sub_policies = []
        sub_policies, answers = self._get_sub_policies(policy, subject)

        # Include policy if remote rule file is missing.
        if not answers:
            return True

        # Include any failure fetching/parsing remote rule file in the
        # decision.
        if any(not answer.is_satisfied for answer in answers):
            return True

        return any(sub_policy.matches(**attributes) for sub_policy in sub_policies)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'required': self.required,
            'sources': self.sources,
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
        'valid_since': SafeYAMLDateTime(optional=True),
        'valid_until': SafeYAMLDateTime(optional=True),
    }

    def check(self, policy, rule_context):
        if self.valid_since or self.valid_until:
            koji_url = current_app.config["KOJI_BASE_URL"]
            subject_creation_time = greenwave.resources.retrieve_koji_build_creation_time(
                rule_context.subject.identifier, koji_url)
            if self.valid_since and subject_creation_time < self.valid_since:
                return []
            if self.valid_until and self.valid_until <= subject_creation_time:
                return []

        matching_results = rule_context.get_results(self.test_case_name)

        if self.scenario is not None:
            matching_results = [
                result for result in matching_results
                if self.scenario in result['data'].get('scenario', [])]

        # Investigate the absence of result first.
        if not matching_results:
            return [
                TestResultMissing(
                    rule_context.subject, self.test_case_name, self.scenario, policy.source)
            ]

        # If we find multiple matching results, we always use the first one which
        # will be the latest chronologically, because ResultsDB always returns
        # results ordered by `submit_time` descending.
        return [
            self._answer_for_result(result, rule_context.subject, policy.source)
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

    def _answer_for_result(self, result, subject, source):
        outcome = result['outcome']

        additional_keys = current_app.config['DISTINCT_LATEST_RESULTS_ON']
        data = {
            key: (result['data'].get(key) or [None])[0]
            for key in additional_keys
        }

        if outcome in current_app.config['OUTCOMES_PASSED']:
            log.debug('Test result passed for the result_id %s and testcase %s,'
                      ' because the outcome is %s', result['id'], self.test_case_name,
                      outcome)
            return TestResultPassed(subject, self.test_case_name, source, result['id'], data)

        if outcome in current_app.config['OUTCOMES_INCOMPLETE']:
            log.debug('Test result MISSING for the %s and '
                      'testcase %s, because the outcome is %s', subject,
                      self.test_case_name, outcome)
            return TestResultIncomplete(subject, self.test_case_name, source, result['id'], data)

        if outcome in current_app.config['OUTCOMES_ERROR']:
            error_reason = result.get('error_reason')
            log.debug('Test result ERROR for the %s and '
                      'testcase %s, because the outcome is %s; error reason: %s',
                      subject, self.test_case_name, outcome, error_reason)
            return TestResultErrored(
                subject, self.test_case_name, source, result['id'], data,
                error_reason)

        log.debug('Test result failed for the %s and '
                  'testcase %s, because the outcome is %s and it didn\'t match any of the '
                  'previous cases', subject, self.test_case_name, outcome)

        return TestResultFailed(subject, self.test_case_name, source, result['id'], data)


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

    def check(self, policy, rule_context):
        raise ValueError('This rule is obsolete and can\'t be checked')


class PackageSpecificBuild(ObsoleteRule):
    yaml_tag = '!PackageSpecificBuild'
    advice = 'Please use the "packages" allowlist instead.'


class FedoraAtomicCi(PackageSpecificBuild):
    yaml_tag = '!FedoraAtomicCi'


class Policy(SafeYAMLObject):
    root_yaml_tag: Optional[str] = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(),
        'product_versions': SafeYAMLList(str),
        'decision_context': SafeYAMLString(optional=True),
        'decision_contexts': SafeYAMLList(str, optional=True, default=list()),
        'subject_type': SafeYAMLString(),
        'rules': SafeYAMLList(Rule),
        'excluded_packages': SafeYAMLList(str, optional=True),
        'packages': SafeYAMLList(str, optional=True),
        'relevance_key': SafeYAMLString(optional=True),
        'relevance_value': SafeYAMLString(optional=True),
    }

    source = None

    def validate(self):
        if not self.decision_context and not self.decision_contexts:
            raise SafeYAMLError('No decision contexts provided')
        if self.decision_context and self.decision_contexts:
            raise SafeYAMLError(
                'Both properties "decision_contexts" and "decision_context" were set'
            )
        super().validate()

    def matches(self, **attributes):
        """
        Returns True only if policy matches provided attributes.

        If an attribute to match is missing it's treated as irrelevant, i.e."match anything".

        Unknown attributes are ignored.

        There must be at least one matching rule or no rules in the policy.
        """
        decision_contexts = attributes.get('decision_context')
        if decision_contexts and not isinstance(decision_contexts, list):
            decision_contexts = [decision_contexts]
        if decision_contexts and not any(context in self.all_decision_contexts
                                         for context in decision_contexts):
            return False

        product_version = attributes.get('product_version')
        if product_version and not self.matches_product_version(product_version):
            return False

        if not self.matches_subject_type(**attributes):
            return False

        return not self.rules or any(rule.matches(self, **attributes) for rule in self.rules)

    def matches_subject_type(self, **attributes):
        subject = attributes.get('subject')
        return not subject or subject.subject_type.matches(self.subject_type)

    def matches_sub_policy(self, sub_policy):
        return set(sub_policy.all_decision_contexts).intersection(self.all_decision_contexts)

    def check(self, rule_context):
        name = rule_context.subject.package_name
        if name:
            for exclude in self.excluded_packages:
                if fnmatch(name, exclude):
                    return [ExcludedInPolicy(rule_context.subject.identifier, self)]
            if self.packages and not any(fnmatch(name, package) for package in self.packages):
                # If the `packages` allowlist is set and this package isn't in the
                # `packages` allowlist, then the policy doesn't apply to it
                return []

        answers = []
        for rule in self.rules:
            answers.extend(rule_context.verify(self, rule))
        return answers

    def matches_product_version(self, product_version):
        return any(fnmatch(product_version, version) for version in self.product_versions)

    @property
    def safe_yaml_label(self):
        return 'Policy {!r}'.format(self.id or 'untitled')

    @property
    def all_decision_contexts(self):
        if self.decision_contexts:
            return self.decision_contexts
        if self.decision_context:
            return [self.decision_context]
        raise SafeYAMLError('No decision contexts provided')


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

    def matches_sub_policy(self, sub_policy):
        return any(sub_policy.matches_product_version(pv) for pv in self.product_versions)


class RemotePolicy(Policy):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(optional=True),
        'product_versions': SafeYAMLList(str, default=['*'], optional=True),
        'subject_type': SafeYAMLString(optional=True, default='koji_build'),
        'decision_context': SafeYAMLString(optional=True),
        'decision_contexts': SafeYAMLList(str, optional=True),
        'rules': SafeYAMLList(Rule),
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
    parent_dcs = set()
    for parent_policy in current_app.config['policies']:
        parent_dcs.update(set(parent_policy.all_decision_contexts))
    for policy in policies:
        missing_decision_contexts.update(
            set(policy.all_decision_contexts).difference(parent_dcs)
        )
    return list(missing_decision_contexts)
