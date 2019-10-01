# SPDX-License-Identifier: GPL-2.0+

from greenwave.policies import (
    InvalidGatingYaml,
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
        type='test-result-passed',
        testcase='test1',
        result_id=99,
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
        InvalidGatingYaml(
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
