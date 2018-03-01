# SPDX-License-Identifier: GPL-2.0+

import yaml


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
    if failure_count:
        return ('{} of {} required tests failed'.format(failure_count, len(answers)))
    missing_count = len([answer for answer in answers if isinstance(answer, TestResultMissing)])
    if missing_count == len(answers):
        return 'no test results found'
    elif missing_count:
        return '{} of {} required tests not found'.format(missing_count, len(answers))
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


class Policy(yaml.YAMLObject):
    yaml_tag = u'!Policy'
    yaml_loader = yaml.SafeLoader

    def applies_to(self, decision_context, product_version):
        return (decision_context == self.decision_context and
                product_version in self.product_versions)

    def check(self, item, results, waivers):
        # If an item is about a package and it is in the blacklist, return RuleSatisfied()
        for package in self.blacklist:
            if (item.get('type') == 'koji_build' and
                    item.get('item') and
                    item['item'].rsplit('-', 2)[0] == package):
                return [RuleSatisfied() for rule in self.rules]
        return [rule.check(item, results, waivers) for rule in self.rules]

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
        }
