# SPDX-License-Identifier: GPL-2.0+
from greenwave.policies import (
    summarize_answers,
    RuleSatisfied,
    TestResultErrored,
    TestResultFailed,
    TestResultMissing,
    TestResultMissingWaived,
    InvalidRemoteRuleYaml,
)

from greenwave.subjects.subject import Subject
from greenwave.subjects.subject_type import GenericSubjectType


testSubject = Subject(GenericSubjectType('koji_build'), 'nethack-1.2.3-1.el9000')
testResultPassed = RuleSatisfied()
testResultErrored = TestResultErrored(
    testSubject, 'test', None, 1, 'some error')
testResultFailed = TestResultFailed(
    testSubject, 'test', None, 1)
testResultMissing = TestResultMissing(
    testSubject, 'test', None)
testResultMissingWaived = TestResultMissingWaived(
    testSubject, 'test', None)
testInvalidGatingYaml = InvalidRemoteRuleYaml(
    testSubject, 'test', 'Missing !Policy tag')


def test_summary_passed():
    answers = [
        testResultPassed,
    ]
    assert summarize_answers(answers) == 'All required tests passed'


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
    assert summarize_answers(answers) == 'All required tests passed'


def test_summary_errored():
    answers = [
        testResultErrored,
    ]
    assert summarize_answers(answers) == '1 of 1 required tests failed (1 error)'


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
    assert summarize_answers(answers) == 'All required tests passed'


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


def test_summary_one_passed_one_failed_one_missing_two_errored():
    answers = [
        testResultErrored,
        testResultPassed,
        testResultFailed,
        testResultMissing,
        testResultErrored,
    ]
    assert summarize_answers(answers) == '3 of 5 required tests failed, 1 result missing (2 errors)'


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
