# SPDX-License-Identifier: GPL-2.0+

from fnmatch import fnmatch
import logging
import re
import greenwave.resources

from greenwave.safe_yaml import (
    SafeYAMLChoice,
    SafeYAMLList,
    SafeYAMLObject,
    SafeYAMLString,
    SafeYAMLError,
)

log = logging.getLogger(__name__)


class DisallowedRuleError(RuntimeError):
    pass


def subject_type_identifier_to_item(subject_type, subject_identifier):
    """
    Greenwave < 0.8 included an "item" key in the "unsatisfied_requirements".
    This returns a suitable value for that key, for backwards compatibility.
    """
    if subject_type == 'bodhi_update':
        return {'type': 'bodhi_update', 'item': subject_identifier}
    elif subject_type == 'koji_build':
        return {'type': 'koji_build', 'item': subject_identifier}
    elif subject_type == 'compose':
        return {'productmd.compose.id': subject_identifier}
    else:
        raise RuntimeError('Unrecognised subject type: %s' % subject_type)


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


class TestCaseNotApplicable(RuleSatisfied):
    """
    A required test case is not applicable to given subject.
    """
    def __init__(self, subject_type, subject_identifier, test_case_name):
        self.subject_type = subject_type
        self.subject_identifier = subject_identifier
        self.test_case_name = test_case_name

    def to_json(self):
        return {
            'type': 'test-case-not-applicable',
            'testcase': self.test_case_name,
            'subject_type': self.subject_type,
            'subject_identifier': self.subject_identifier,
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
        return 'all required tests passed'

    assert False, 'Unexpected unsatisfied result'
    return 'inexplicable result'


class Rule(SafeYAMLObject):
    """
    An individual rule within a policy. A policy consists of multiple rules.
    When the policy is evaluated, each rule returns an answer
    (instance of :py:class:`Answer`).

    This base class is not used directly.
    """
    def check(self, subject_type, subject_identifier, results, waivers):
        """
        Evaluate this policy rule for the given item.

        Args:
            subject_type (str): Type of thing we are making a decision about
                (for example, 'koji_build', 'bodhi_update', ...)
            subject_identifier (str): Item we are making a decision about (for
                example, Koji build NVR, Bodhi update id, ...)
            results (list): List of result objects looked up in ResultsDB for this item.
            waivers (list): List of waiver objects looked up in WaiverDB for the results.

        Returns:
            Answer: An instance of a subclass of :py:class:`Answer` describing the result.
        """
        raise NotImplementedError()


def waives_invalid_gating_yaml(waiver, subject_type, subject_identifier):
    return (waiver['testcase'] == 'invalid-gating-yaml' and
            waiver['subject']['type'] == subject_type and
            waiver['subject']['item'] == subject_identifier)


class RemoteRule(Rule):
    yaml_tag = '!RemoteRule'
    safe_yaml_attributes = {}

    def check(self, subject_type, subject_identifier, results, waivers):
        if subject_type != 'koji_build':
            return []

        pkg_name = subject_identifier.rsplit('-', 2)[0]
        pkg_namespace, rev = greenwave.resources.retrieve_scm_from_koji(subject_identifier)
        # if the element is actually a container and not a pkg there will be a "-container"
        # string at the end of the "pkg_name" and it will not match with the one in the
        # gating.yaml URL
        if pkg_namespace == 'containers':
            pkg_name = re.sub('-container$', '', pkg_name)
        response = greenwave.resources.retrieve_yaml_remote_rule(rev, pkg_name, pkg_namespace)

        if response is None:
            # greenwave extension file not found
            return []

        try:
            policies = RemotePolicy.safe_load_all(response)
        except SafeYAMLError as e:
            if any(waives_invalid_gating_yaml(waiver, subject_type, subject_identifier)
                    for waiver in waivers):
                return []
            return [
                InvalidGatingYaml(
                    subject_type, subject_identifier, 'invalid-gating-yaml', str(e))
            ]

        answers = []
        for policy in policies:
            response = policy.check(subject_identifier, results, waivers)
            if isinstance(response, list):
                answers.extend(response)
            else:
                answers.append(response)
        return answers

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

    def check(self, subject_type, subject_identifier, results, waivers):
        matching_results = [
            r for r in results if r['testcase']['name'] == self.test_case_name]
        matching_waivers = [
            w for w in waivers if (w['testcase'] == self.test_case_name and w['waived'] is True)]

        # Rules may optionally specify a scenario to limit applicability.
        if self.scenario:
            matching_results = [r for r in matching_results if self.scenario in
                                r['data'].get('scenario', [])]

        # Investigate the absence of results first.
        if not matching_results:
            if not matching_waivers:
                return TestResultMissing(subject_type, subject_identifier, self.test_case_name,
                                         self.scenario)
            return TestResultMissingWaived(
                subject_type, subject_identifier, self.test_case_name, self.scenario)

        # For compose make decisions based on all architectures and variants.
        if subject_type == 'compose':
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
                    answers.append(
                        self._answer_for_result(result, waivers, subject_type, subject_identifier))

            return answers

        # If we find multiple matching results, we always use the first one which
        # will be the latest chronologically, because ResultsDB always returns
        # results ordered by `submit_time` descending.
        matching_result = matching_results[0]
        return self._answer_for_result(matching_result, waivers, subject_type, subject_identifier)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'scenario': self.scenario,
        }

    def _answer_for_result(self, result, waivers, subject_type, subject_identifier):
        if result['outcome'] in ['PASSED', 'INFO']:
            return TestResultPassed(self.test_case_name, result['id'])

        # TODO limit who is allowed to waive

        matching_waivers = [w for w in waivers if (
            w['subject_type'] == subject_type and
            w['subject_identifier'] == result['data']['item'][0] and
            w['testcase'] == result['testcase']['name']
        )]
        if matching_waivers:
            return TestResultPassed(self.test_case_name, result['id'])
        return TestResultFailed(subject_type, subject_identifier, self.test_case_name,
                                self.scenario, result['id'])


class PackageSpecificRule(Rule):
    """
    This rule only applies itself to results which are for its configured
    list of packages (called "repos").

    This intermediary class should be considered abstract, and not used directly.
    """

    safe_yaml_attributes = {
        'test_case_name': SafeYAMLString(),
        'repos': SafeYAMLList(str),
    }

    def check(self, subject_type, subject_identifier, results, waivers):
        """ Check that the subject passes testcase for the given results, but
        only if the subject is a build of a package name configured for
        this rule, specified by "repos".  Any of the repos may be a glob.

        If this rule is used in a policy for some subject type other than
        "koji_build" (which makes no sense), the rule is considered satisfied
        (ignored).

        Subjects whose package names (extracted from their NVR) do not match
        any of the globs in the "repos" list of this rule are considered
        satisfied (ignored).
        """

        if subject_type != 'koji_build':
            return TestCaseNotApplicable(subject_type, subject_identifier, self.test_case_name)

        pkg_name = subject_identifier.rsplit('-', 2)[0]
        if not any(fnmatch(pkg_name, repo) for repo in self.repos):
            return TestCaseNotApplicable(subject_type, subject_identifier, self.test_case_name)

        rule = PassingTestCaseRule()
        # pylint: disable=attribute-defined-outside-init
        rule.test_case_name = self.test_case_name
        return rule.check(subject_type, subject_identifier, results, waivers)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'repos': self.repos,
        }


class FedoraAtomicCi(PackageSpecificRule):
    yaml_tag = '!FedoraAtomicCi'


class PackageSpecificBuild(PackageSpecificRule):
    yaml_tag = '!PackageSpecificBuild'


class Policy(SafeYAMLObject):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(),
        'product_versions': SafeYAMLList(str),
        'decision_context': SafeYAMLString(),
        # TODO: Handle brew-build value better.
        'subject_type': SafeYAMLChoice(
            'koji_build', 'bodhi_update', 'compose', 'brew-build'),
        'rules': SafeYAMLList(Rule),
        'blacklist': SafeYAMLList(str, optional=True),
        'relevance_key': SafeYAMLString(optional=True),
        'relevance_value': SafeYAMLString(optional=True),
    }

    def applies_to(self, decision_context, product_version, subject_type):
        return (decision_context == self.decision_context and
                self._applies_to_product_version(product_version) and
                subject_type == self.subject_type)

    def check(self, subject_identifier, results, waivers):
        # If an item is about a package and it is in the blacklist, return RuleSatisfied()
        if self.subject_type == 'koji_build':
            name = subject_identifier.rsplit('-', 2)[0]
            if name in self.blacklist:
                return [BlacklistedInPolicy(subject_identifier) for rule in self.rules]
        answers = []
        for rule in self.rules:
            response = rule.check(self.subject_type, subject_identifier, results, waivers)
            if isinstance(response, list):
                answers.extend(response)
            else:
                answers.append(response)
        return answers

    def _applies_to_product_version(self, product_version):
        return any(fnmatch(product_version, version) for version in self.product_versions)

    @property
    def safe_yaml_label(self):
        return 'Policy {!r}'.format(self.id or 'untitled')


class RemotePolicy(Policy):
    root_yaml_tag = '!Policy'

    safe_yaml_attributes = {
        'id': SafeYAMLString(optional=True),
        'product_versions': SafeYAMLList(str),
        'decision_context': SafeYAMLString(),
        'rules': SafeYAMLList(Rule),
        'blacklist': SafeYAMLList(str, optional=True),
    }

    subject_type = 'koji_build'

    def validate(self):
        for rule in self.rules:
            if isinstance(rule, RemoteRule):
                raise SafeYAMLError('RemoteRule is not allowed in remote policies')
        super().validate()
