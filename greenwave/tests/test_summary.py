# SPDX-License-Identifier: GPL-2.0+
from greenwave.policies import (
    summarize_answers,
    RuleSatisfied,
    TestResultFailed,
    TestResultMissing,
    TestResultMissingWaived,
    InvalidGatingYaml,
)


testResultPassed = RuleSatisfied()
testResultFailed = TestResultFailed(
    'koji_build', 'nethack-1.2.3-1.el9000', 'test', None, 1)
testResultMissing = TestResultMissing(
    'koji_build', 'nethack-1.2.3-1.el9000', 'test', None)
testResultMissingWaived = TestResultMissingWaived(
    'koji_build', 'nethack-1.2.3-1.el9000', 'test', None)
testInvalidGatingYaml = InvalidGatingYaml(
    'koji_build', 'nethack-1.2.3-1.el9000', 'test', 'Missing !Policy tag')


def test_summary_passed():
    answers = [
        testResultPassed,
    ]
    assert summarize_answers(answers) == 'all required tests passed'


def test_summary_empty():
    answers = []
    assert summarize_answers(answers) == 'no tests are required'


def test_summary_failed():
    answers = [
        testResultFailed,
    ]
    assert summarize_answers(answers) == '1 of 1 required tests failed'


def test_summary_missing():
    answers = [
        testResultMissing,
    ]
    assert summarize_answers(answers) == '1 of 1 required test results missing'


def test_summary_missing_waived():
    answers = [
        testResultMissingWaived,
    ]
    assert summarize_answers(answers) == 'all required tests passed'


def test_summary_one_passed_one_failed():
    answers = [
        testResultPassed,
        testResultFailed,
    ]
    assert summarize_answers(answers) == '1 of 2 required tests failed'


def test_summary_one_passed_one_missing():
    answers = [
        testResultPassed,
        testResultMissing,
    ]
    assert summarize_answers(answers) == '1 of 2 required test results missing'


def test_summary_one_passed_one_missing_waived():
    answers = [
        testResultPassed,
        testResultMissingWaived,
    ]
    assert summarize_answers(answers) == 'all required tests passed'


def test_summary_one_failed_one_missing():
    answers = [
        testResultFailed,
        testResultMissing,
    ]
    assert summarize_answers(answers) == '1 of 2 required tests failed, 1 result missing'


def test_summary_one_passed_one_failed_one_missing():
    answers = [
        testResultPassed,
        testResultFailed,
        testResultMissing,
    ]
    assert summarize_answers(answers) == '1 of 3 required tests failed, 1 result missing'


def test_summary_invalid_gating_yaml():
    answers = [
        testInvalidGatingYaml,
    ]
    assert summarize_answers(answers) == '1 of 1 required tests failed'


def test_summary_one_passed_one_invalid_gating_yaml_one_missing():
    answers = [
        testResultPassed,
        testResultMissing,
        testInvalidGatingYaml,
    ]
    assert summarize_answers(answers) == '1 of 3 required tests failed, 1 result missing'
