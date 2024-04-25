# SPDX-License-Identifier: GPL-2.0+
from greenwave.policies import (
    InvalidRemoteRuleYaml,
    RuleSatisfied,
    TestResultErrored,
    TestResultFailed,
    TestResultIncomplete,
    TestResultMissing,
    TestResultWaived,
    summarize_answers,
)
from greenwave.subjects.subject import Subject
from greenwave.subjects.subject_type import GenericSubjectType

testSubject = Subject(GenericSubjectType("koji_build"), "nethack-1.2.3-1.el9000")
testResultPassed = RuleSatisfied()
testResultErrored = TestResultErrored(testSubject, "test", None, 1, {}, "some error")
testResultFailed = TestResultFailed(testSubject, "test", None, 1, {})
testResultIncomplete = TestResultIncomplete(testSubject, "test", None, 1, {})
testResultMissing = TestResultMissing(testSubject, "test", None, None)
testInvalidGatingYaml = InvalidRemoteRuleYaml(
    testSubject, "test", "Missing !Policy tag", None
)


def test_summary_passed():
    answers = [
        testResultPassed,
    ]
    assert (
        summarize_answers(answers)
        == "All required tests (1 total) have passed or been waived"
    )


def test_summary_empty():
    answers = []
    assert summarize_answers(answers) == "No tests are required"


def test_summary_failed():
    answers = [
        testResultFailed,
    ]
    assert summarize_answers(answers) == "Of 1 required test, 1 test failed"


def test_summary_incomplete():
    answers = [
        testResultIncomplete,
    ]
    assert summarize_answers(answers) == "Of 1 required test, 1 test incomplete"


def test_summary_missing():
    answers = [
        testResultMissing,
    ]
    assert summarize_answers(answers) == "Of 1 required test, 1 result missing"


def test_summary_missing_waived():
    answers = [
        TestResultWaived(testResultMissing, 123),
    ]
    assert (
        summarize_answers(answers)
        == "All required tests (1 total) have passed or been waived"
    )


def test_summary_errored():
    answers = [
        testResultErrored,
    ]
    assert summarize_answers(answers) == "Of 1 required test, 1 test errored"


def test_summary_one_passed_one_failed():
    answers = [
        testResultPassed,
        testResultFailed,
    ]
    assert summarize_answers(answers) == "Of 2 required tests, 1 test failed"


def test_summary_one_passed_one_missing():
    answers = [
        testResultPassed,
        testResultMissing,
    ]
    assert summarize_answers(answers) == "Of 2 required tests, 1 result missing"


def test_summary_one_passed_one_missing_waived():
    answers = [
        testResultPassed,
        TestResultWaived(testResultMissing, 123),
    ]
    assert (
        summarize_answers(answers)
        == "All required tests (2 total) have passed or been waived"
    )


def test_summary_one_failed_one_missing():
    answers = [
        testResultFailed,
        testResultMissing,
    ]
    exp = "Of 2 required tests, 1 result missing, 1 test failed"
    assert summarize_answers(answers) == exp


def test_summary_one_passed_one_failed_one_missing():
    answers = [
        testResultPassed,
        testResultFailed,
        testResultMissing,
    ]
    exp = "Of 3 required tests, 1 result missing, 1 test failed"
    assert summarize_answers(answers) == exp


def test_summary_one_passed_one_failed_one_missing_two_errored():
    answers = [
        testResultErrored,
        testResultPassed,
        testResultFailed,
        testResultMissing,
        testResultErrored,
    ]
    exp = "Of 5 required tests, 1 result missing, 2 tests errored, 1 test failed"
    assert summarize_answers(answers) == exp


def test_summary_invalid_gating_yaml():
    answers = [
        testInvalidGatingYaml,
    ]
    exp = "1 error due to invalid remote rule file"
    assert summarize_answers(answers) == exp


def test_summary_one_passed_one_invalid_gating_yaml_one_missing():
    answers = [
        testResultPassed,
        testResultMissing,
        testInvalidGatingYaml,
    ]
    exp = "1 error due to invalid remote rule file. "
    exp += "Of 2 required tests, 1 result missing"
    assert summarize_answers(answers) == exp
