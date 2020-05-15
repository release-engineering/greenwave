# SPDX-License-Identifier: GPL-2.0+

import mock

from greenwave.policies import (
    InvalidRemoteRuleYaml,
    TestResultPassed,
    TestResultMissing,
    TestResultFailed,
)
from greenwave.subjects.subject import Subject
from greenwave.subjects.subject_type import GenericSubjectType
from greenwave.waivers import waive_answers


def test_subject():
    return Subject(GenericSubjectType('koji_build'), 'nethack-1.2.3-1.rawhide')


def test_waive_failed_result():
    answers = [
        TestResultFailed(
            subject=test_subject(),
            test_case_name='test1',
            scenario='scenario1',
            result_id=99,
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
        )
    ]
    waived = waive_answers(answers, waivers)
    expected_json = dict(
        type='test-result-failed-waived',
        testcase='test1',
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        result_id=99,
        scenario='scenario1',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_missing_result():
    answers = [
        TestResultMissing(
            subject=test_subject(),
            test_case_name='test1',
            scenario='scenario1',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
        )
    ]
    waived = waive_answers(answers, waivers)
    expected_json = dict(
        type='test-result-missing-waived',
        testcase='test1',
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        scenario='scenario1',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_invalid_gatin_yaml():
    answers = [
        InvalidRemoteRuleYaml(
            subject=test_subject(),
            test_case_name='invalid-gating-yaml',
            details='',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='invalid-gating-yaml',
        )
    ]
    waived = waive_answers(answers, waivers)
    assert [] == waived


def test_waive_answers_duplicates():
    mock_subject = mock.Mock()
    mock_subject.type = 'koji_build'
    mock_subject.identifier = 'glibc-1.0-1588233006.954829.fedora-rawhide'
    mock_subject.to_dict.return_value = {'item': mock_subject.identifier, 'type': mock_subject.type}
    test_name1 = 'test1'
    test_name2 = 'test2'
    scenario = 'xyz'
    result_id = 123456
    answers = [
        TestResultPassed(mock_subject, test_name1, result_id),
        TestResultMissing(mock_subject, test_name2, scenario),
        TestResultFailed(mock_subject, test_name1, scenario, result_id),
        TestResultPassed(mock_subject, test_name1, result_id),
        TestResultMissing(mock_subject, test_name2, scenario),
        TestResultFailed(mock_subject, test_name2, scenario, result_id)
    ]
    waivers = [
        {
            "subject_identifier": mock_subject.identifier,
            "subject_type": mock_subject.type,
            'testcase': test_name2
        }
    ]
    answers_json = [ans.to_json() for ans in waive_answers(answers, waivers)]
    answers_to_check = [
        {
            "subject_identifier": mock_subject.identifier,
            "subject_type": mock_subject.type,
            "testcase": test_name1,
            'result_id': result_id,
            "type": "test-result-passed"
        },
        {
            "scenario": scenario,
            "subject_identifier": mock_subject.identifier,
            "subject_type": mock_subject.type,
            "testcase": test_name2,
            "type": "test-result-missing-waived"
        },
        {
            "item": {
                "item": mock_subject.identifier,
                "type": mock_subject.type
            },
            "scenario": scenario,
            "testcase": test_name1,
            'result_id': result_id,
            "type": "test-result-failed"
        },
        {
            "scenario": scenario,
            "subject_identifier": mock_subject.identifier,
            "subject_type": mock_subject.type,
            "testcase": test_name2,
            'result_id': result_id,
            "type": "test-result-failed-waived"
        },
    ]
    assert len(answers_json) == len(answers_to_check)
    assert all(a in answers_json for a in answers_to_check)
