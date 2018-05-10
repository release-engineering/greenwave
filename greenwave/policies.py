# SPDX-License-Identifier: GPL-2.0+

from fnmatch import fnmatch
import yaml
import greenwave.resources


def validate_policies(policies, disallowed_rules=None):
    disallowed_rules = disallowed_rules or []
    for policy in policies:
        if not isinstance(policy, Policy):
            raise RuntimeError('Policies are not configured properly as policy %s '
                               'is not an instance of Policy' % policy)
        for rule in policy.rules:
            if not isinstance(rule, Rule):
                raise RuntimeError('Policies are not configured properly as rule %s '
                                   'is not an instance of Rule' % rule)
            for disallowed_rule in disallowed_rules:
                if isinstance(rule, disallowed_rule):
                    raise RuntimeError('Policies are not configured properly as rule %s '
                                       'is an instance of %s' % (rule, disallowed_rule))


class Answer(object):
    """
    Represents the result of evaluating a policy rule against a particular
    item. But we call it an "answer" because the word "result" is a bit
    overloaded in here. :-)

    This base class is not used directly -- each answer is an instance of
    a subclass, depending on what the answer was.
    """

    pass


class RuleSatisfied(Answer):
    """
    The rule's requirements are satisfied for this item.
    """

    is_satisfied = True


class RuleNotSatisfied(Answer):
    """
    The rule's requirements are not satisfied for this item.

    Not used directly -- the answer is an instance of a subclass, specifying
    exactly what was not satisfied.
    """

    is_satisfied = False

    def to_json(self):
        """
        Returns a machine-readable description of the problem for API responses.
        """
        raise NotImplementedError()


class TestResultMissing(RuleNotSatisfied):
    """
    A required test case is missing (that is, we did not find any result in
    ResultsDB with a matching item and test case name).
    """

    def __init__(self, item, test_case_name, scenario):
        self.item = item
        self.test_case_name = test_case_name
        self.scenario = scenario

    def to_json(self):
        return {
            'type': 'test-result-missing',
            'item': self.item,
            'testcase': self.test_case_name,
            'scenario': self.scenario,
        }


class TestResultFailed(RuleNotSatisfied):
    """
    A required test case did not pass (that is, its outcome in ResultsDB was
    not ``PASSED`` or ``INFO``) and no corresponding waiver was found.
    """

    def __init__(self, item, test_case_name, scenario, result_id):
        self.item = item
        self.test_case_name = test_case_name
        self.scenario = scenario
        self.result_id = result_id

    def to_json(self):
        return {
            'type': 'test-result-failed',
            'item': self.item,
            'testcase': self.test_case_name,
            'scenario': self.scenario,
            'result_id': self.result_id,
        }


def summarize_answers(answers):
    """
    Produces a one-sentence human-readable summary of the result of evaluating a policy.

    Args:
        answers (list): List of :py:class:`Answers <Answer>` from evaluating a policy.

    Returns:
        str: Human-readable summary.
    """
    if len(answers) == 0:
        return 'no tests are required'
    if all(answer.is_satisfied for answer in answers):
        return 'all required tests passed'
    failure_count = len([answer for answer in answers if isinstance(answer, TestResultFailed)])
    missing_count = len([answer for answer in answers if isinstance(answer, TestResultMissing)])
    if failure_count and missing_count:
        return '{} of {} required tests failed, {} result{} missing'.format(
            failure_count, len(answers), missing_count, 's' if missing_count > 1 else '')
    elif failure_count:
        return '{} of {} required tests failed'.format(failure_count, len(answers))
    elif missing_count:
        return '{} of {} required test results missing'.format(missing_count, len(answers))
    return 'inexplicable result'


class Rule(yaml.YAMLObject):
    """
    An individual rule within a policy. A policy consists of multiple rules.
    When the policy is evaluated, each rule returns an answer
    (instance of :py:class:`Answer`).

    This base class is not used directly.
    """
    def check(self, item, results, waivers):
        """
        Evaluate this policy rule for the given item.

        Args:
            item (dict): The item we are evaluating (one or more key-value pairs
                of 'data' key in ResultsDB, for example {"type": "koji_build",
                "item": "xscreensaver-5.37-3.fc27"}).
            results (list): List of result objects looked up in ResultsDB for this item.
            waivers (list): List of waiver objects looked up in WaiverDB for the results.

        Returns:
            Answer: An instance of a subclass of :py:class:`Answer` describing the result.
        """
        raise NotImplementedError()

    def to_json(self):
        """ Return a dict representation of this rule.

        Returns:
            dict: A representation of this Rule as a dict for an API response.
        """
        raise NotImplementedError()


class RemoteOriginalSpecNvrRule(Rule):
    yaml_tag = u'!RemoteOriginalSpecNvrRule'
    yaml_loader = yaml.SafeLoader

    def check(self, item, results, waivers):
        pkg_name = item['original_spec_nvr'].rsplit('-', 2)[0]
        rev = greenwave.resources.retrieve_rev_from_koji(item['original_spec_nvr'])
        response = greenwave.resources.retrieve_yaml_remote_original_spec_nvr_rule(rev, pkg_name)

        if isinstance(response, RuleSatisfied):
            # greenwave extension file not found
            return RuleSatisfied()
        else:
            policies = yaml.safe_load_all(response)
            # policies is a generator, so listifying it
            policies = list(policies)
            validate_policies(policies, [RemoteOriginalSpecNvrRule])
            answers = []
            for policy in policies:
                response = policy.check(item, results, waivers)
                if isinstance(response, list):
                    answers.extend(response)
                else:
                    answers.append(response)
            return answers

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
        }


class PassingTestCaseRule(Rule):
    """
    This rule requires either a passing result for the given test case, or
    a non-passing result with a waiver.
    """
    yaml_tag = u'!PassingTestCaseRule'
    yaml_loader = yaml.SafeLoader

    def check(self, item, results, waivers):
        matching_results = [
            r for r in results if r['testcase']['name'] == self.test_case_name]
        matching_waivers = [
            w for w in waivers if (w['testcase'] == self.test_case_name and w['waived'] is True)]

        # Rules may optionally specify a scenario to limit applicability.
        if self._scenario:
            matching_results = [r for r in matching_results if self.scenario in
                                r['data'].get('scenario', [])]

        # Investigate the absence of results first.
        if not matching_results:
            if not matching_waivers:
                return TestResultMissing(item, self.test_case_name, self._scenario)
            else:
                # The result is absent, but the absence is waived.
                return RuleSatisfied()

        # If we find multiple matching results, we always use the first one which
        # will be the latest chronologically, because ResultsDB always returns
        # results ordered by `submit_time` descending.
        matching_result = matching_results[0]
        if matching_result['outcome'] in ['PASSED', 'INFO']:
            return RuleSatisfied()

        # XXX limit who is allowed to waive
        if any(w['subject'] == dict([(key, value[0])
               for key, value in matching_result['data'].items()]) and
               w['testcase'] == matching_result['testcase']['name'] and
               w['waived'] for w in waivers):
            return RuleSatisfied()
        return TestResultFailed(item, self.test_case_name, self._scenario, matching_result['id'])

    @property
    def _scenario(self):
        return getattr(self, 'scenario', None)

    def __repr__(self):
        return "%s(test_case_name=%r, scenario=%r)" % (
            self.__class__.__name__, self.test_case_name, self._scenario)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'scenario': self._scenario,
        }


class PackageSpecificRule(Rule):
    """
    This rule only applies itself to results which are for its configured
    list of packages (called "repos").

    This intermediary class should be considered abstract, and not used directly.
    """

    def __init__(self, test_case_name, repos):
        self.test_case_name = test_case_name
        self.repos = repos

    def check(self, item, results, waivers):
        """ Check that the item passes testcase for the given results, but
        only if the item is an instance of a package name configured for
        this rule, specified by "repos".  Any of the repos may be a glob.

        Items which do not bear the "nvr_key" for this rule are considered
        satisfied (ignored).

        Items whose package names (extracted from their NVR) do not match
        any of the globs in the "repos" list of this rule are considered
        satisfied (ignored).
        """

        if self.nvr_key not in item:
            return RuleSatisfied()

        nvr = item[self.nvr_key]
        pkg_name = nvr.rsplit('-', 2)[0]
        if not any(fnmatch(pkg_name, repo) for repo in self.repos):
            return RuleSatisfied()

        rule = PassingTestCaseRule()
        # pylint: disable=attribute-defined-outside-init
        rule.test_case_name = self.test_case_name
        return rule.check(item, results, waivers)

    def __repr__(self):
        return "%s(test_case_name=%s, repos=%r)" % (
            self.__class__.__name__, self.test_case_name, self.repos)

    def to_json(self):
        return {
            'rule': self.__class__.__name__,
            'test_case_name': self.test_case_name,
            'repos': self.repos,
            'nvr_key': self.nvr_key,
        }


class FedoraAtomicCi(PackageSpecificRule):
    yaml_tag = u'!FedoraAtomicCi'
    yaml_loader = yaml.SafeLoader
    nvr_key = 'original_spec_nvr'


class PackageSpecificBuild(PackageSpecificRule):
    yaml_tag = u'!PackageSpecificBuild'
    yaml_loader = yaml.SafeLoader
    nvr_key = 'item'


class Policy(yaml.YAMLObject):
    yaml_tag = u'!Policy'
    yaml_loader = yaml.SafeLoader

    def applies_to(self, decision_context, product_version):
        return (decision_context == self.decision_context and
                self._applies_to_product_version(product_version))

    def is_relevant_to(self, item):
        relevance_key = getattr(self, 'relevance_key', None)
        relevance_value = getattr(self, 'relevance_value', None)

        if relevance_key and relevance_value:
            return item.get(relevance_key) == relevance_value

        if relevance_key:
            return relevance_key in item

        if relevance_value:
            return relevance_value in item.values()

        return True

    def check(self, item, results, waivers):
        # If an item is about a package and it is in the blacklist, return RuleSatisfied()
        for package in self.blacklist:
            if (item.get('type') == 'koji_build' and
                    item.get('item') and
                    item['item'].rsplit('-', 2)[0] == package):
                return [RuleSatisfied() for rule in self.rules]
        answers = []
        for rule in self.rules:
            response = rule.check(item, results, waivers)
            if isinstance(response, list):
                answers.extend(response)
            else:
                answers.append(response)
        return answers

    def __repr__(self):
        return "%s(id=%r, product_versions=%r, decision_context=%r, rules=%r)" % (
            self.__class__.__name__, self.id, self.product_versions, self.decision_context,
            self.rules)

    def to_json(self):
        return {
            'id': self.id,
            'product_versions': self.product_versions,
            'decision_context': self.decision_context,
            'rules': [rule.to_json() for rule in self.rules],
            'blacklist': self.blacklist,
            'relevance_key': getattr(self, 'relevance_key', None),
            'relevance_value': getattr(self, 'relevance_value', None),
        }

    def _applies_to_product_version(self, product_version):
        return any(fnmatch(product_version, version) for version in self.product_versions)
