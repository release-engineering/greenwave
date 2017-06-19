# SPDX-License-Identifier: GPL-2.0+


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

    def __init__(self, item, test_case_name):
        self.item = item
        self.test_case_name = test_case_name

    def to_json(self):
        return {
            'type': 'test-result-missing',
            'item': self.item,
            'testcase': self.test_case_name,
        }


class TestResultFailed(RuleNotSatisfied):
    """
    A required test case did not pass (that is, its outcome in ResultsDB was
    not ``PASSED`` or ``INFO``) and no corresponding waiver was found.
    """

    def __init__(self, item, test_case_name, result_id):
        self.item = item
        self.test_case_name = test_case_name
        self.result_id = result_id

    def to_json(self):
        return {
            'type': 'test-result-failed',
            'item': self.item,
            'testcase': self.test_case_name,
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


class Rule(object):
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
            item (str): The item we are evaluating ('item' key in ResultsDB,
                        for example a build NVR).
            results (list): List of result objects looked up in ResultsDB for this item.
            waivers (list): List of waiver objects looked up in WaiverDB for the results.

        Returns:
            Answer: An instance of a subclass of :py:class:`Answer` describing the result.
        """
        raise NotImplementedError()


class PassingTestCaseRule(Rule):
    """
    This rule requires either a passing result for the given test case, or
    a non-passing result with a waiver.
    """

    def __init__(self, test_case_name):
        self.test_case_name = test_case_name

    def check(self, item, results, waivers):
        matching_results = [r for r in results if r['testcase']['name'] == self.test_case_name]
        if not matching_results:
            return TestResultMissing(item, self.test_case_name)
        # XXX need to handle multiple results (take the latest)
        matching_result = matching_results[0]
        if matching_result['outcome'] in ['PASSED', 'INFO']:
            return RuleSatisfied()
        # XXX limit who is allowed to waive
        if any(w['result_id'] == matching_result['id'] and w['waived'] for w in waivers):
            return RuleSatisfied()
        return TestResultFailed(item, self.test_case_name, matching_result['id'])


class Policy(object):

    def __init__(self, id, product_versions, decision_context, rules):
        self.id = id
        self.product_versions = frozenset(product_versions)
        self.decision_context = decision_context
        self.rules = rules

    def applies_to(self, decision_context, product_version):
        return (decision_context == self.decision_context and
                product_version in self.product_versions)

    def check(self, item, results, waivers):
        return [rule.check(item, results, waivers) for rule in self.rules]


policies = [
    # Mimic the default Errata rule used for RHEL-7 https://errata.devel.redhat.com/workflow_rules/1
    # In Errata, in order to transition to QE state, an advisory must complete rpmdiff test.
    # A completed rpmdiff test could be some dist.rpmdiff.* testcases in ResultsDB and all the
    # tests need to be passed.
    Policy(
        id='1',
        product_versions=[
            'rhel-7',
        ],
        decision_context='errata_newfile_to_qe',
        rules=[
            PassingTestCaseRule('dist.rpmdiff.analysis.abi_symbols'),
            PassingTestCaseRule('dist.rpmdiff.analysis.binary_stripping'),
            PassingTestCaseRule('dist.rpmdiff.analysis.build_log'),
            PassingTestCaseRule('dist.rpmdiff.analysis.changes_in_rpms'),
            PassingTestCaseRule('dist.rpmdiff.analysis.desktop_file_sanity'),
            PassingTestCaseRule('dist.rpmdiff.analysis.elflint'),
            PassingTestCaseRule('dist.rpmdiff.analysis.empty_payload'),
            PassingTestCaseRule('dist.rpmdiff.analysis.execshield'),
            PassingTestCaseRule('dist.rpmdiff.analysis.file_list'),
            PassingTestCaseRule('dist.rpmdiff.analysis.file_permissions'),
            PassingTestCaseRule('dist.rpmdiff.analysis.file_sizes'),
            PassingTestCaseRule('dist.rpmdiff.analysis.ipv_'),
            PassingTestCaseRule('dist.rpmdiff.analysis.java_byte_code'),
            PassingTestCaseRule('dist.rpmdiff.analysis.kernel_module_parameters'),
            PassingTestCaseRule('dist.rpmdiff.analysis.manpage_integrity'),
            PassingTestCaseRule('dist.rpmdiff.analysis.metadata'),
            PassingTestCaseRule('dist.rpmdiff.analysis.multilib_regressions'),
            PassingTestCaseRule('dist.rpmdiff.analysis.ownership'),
            PassingTestCaseRule('dist.rpmdiff.analysis.patches'),
            PassingTestCaseRule('dist.rpmdiff.analysis.pathnames'),
            PassingTestCaseRule('dist.rpmdiff.analysis.politics'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpath'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpm_changelog'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpm_config_doc_files'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpm_requires_provides'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpm_scripts'),
            PassingTestCaseRule('dist.rpmdiff.analysis.rpm_triggers'),
            PassingTestCaseRule('dist.rpmdiff.analysis.shell_syntax'),
            PassingTestCaseRule('dist.rpmdiff.analysis.specfile_checks'),
            PassingTestCaseRule('dist.rpmdiff.analysis.symlinks'),
            PassingTestCaseRule('dist.rpmdiff.analysis.upstream_source'),
            PassingTestCaseRule('dist.rpmdiff.analysis.virus_scan'),
            PassingTestCaseRule('dist.rpmdiff.analysis.xml_validity'),
            PassingTestCaseRule('dist.rpmdiff.comparison.abi_symbols'),
            PassingTestCaseRule('dist.rpmdiff.comparison.binary_stripping'),
            PassingTestCaseRule('dist.rpmdiff.comparison.build_log'),
            PassingTestCaseRule('dist.rpmdiff.comparison.changed_files'),
            PassingTestCaseRule('dist.rpmdiff.comparison.changes_in_rpms'),
            PassingTestCaseRule('dist.rpmdiff.comparison.desktop_file_sanity'),
            PassingTestCaseRule('dist.rpmdiff.comparison.dt_needed'),
            PassingTestCaseRule('dist.rpmdiff.comparison.elflint'),
            PassingTestCaseRule('dist.rpmdiff.comparison.empty_payload'),
            PassingTestCaseRule('dist.rpmdiff.comparison.execshield'),
            PassingTestCaseRule('dist.rpmdiff.comparison.file_list'),
            PassingTestCaseRule('dist.rpmdiff.comparison.file_permissions'),
            PassingTestCaseRule('dist.rpmdiff.comparison.file_sizes'),
            PassingTestCaseRule('dist.rpmdiff.comparison.files_moving_rpm'),
            PassingTestCaseRule('dist.rpmdiff.comparison.file_types'),
            PassingTestCaseRule('dist.rpmdiff.comparison.ipv_'),
            PassingTestCaseRule('dist.rpmdiff.comparison.java_byte_code'),
            PassingTestCaseRule('dist.rpmdiff.comparison.kernel_module_parameters'),
            PassingTestCaseRule('dist.rpmdiff.comparison.kernel_module_pci_ids'),
            PassingTestCaseRule('dist.rpmdiff.comparison.manpage_integrity'),
            PassingTestCaseRule('dist.rpmdiff.comparison.metadata'),
            PassingTestCaseRule('dist.rpmdiff.comparison.multilib_regressions'),
            PassingTestCaseRule('dist.rpmdiff.comparison.ownership'),
            PassingTestCaseRule('dist.rpmdiff.comparison.patches'),
            PassingTestCaseRule('dist.rpmdiff.comparison.pathnames'),
            PassingTestCaseRule('dist.rpmdiff.comparison.politics'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpath'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpm_changelog'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpm_config_doc_files'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpm_requires_provides'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpm_scripts'),
            PassingTestCaseRule('dist.rpmdiff.comparison.rpm_triggers'),
            PassingTestCaseRule('dist.rpmdiff.comparison.shell_syntax'),
            PassingTestCaseRule('dist.rpmdiff.comparison.specfile_checks'),
            PassingTestCaseRule('dist.rpmdiff.comparison.symlinks'),
            PassingTestCaseRule('dist.rpmdiff.comparison.upstream_source'),
            PassingTestCaseRule('dist.rpmdiff.comparison.virus_scan'),
            PassingTestCaseRule('dist.rpmdiff.comparison.xml_validity'),
        ],
    ),
]
