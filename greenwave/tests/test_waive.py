# SPDX-License-Identifier: GPL-2.0+
from greenwave.policies import (
    InvalidRemoteRuleYaml,
    TestResultErrored,
    TestResultFailed,
    TestResultIncomplete,
    TestResultMissing,
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
            source='https://greenwave_tests.example.com',
            result_id=99,
            data={'scenario': 'scenario1'},
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
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
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_missing_result():
    answers = [
        TestResultMissing(
            subject=test_subject(),
            test_case_name='test1',
            scenario='scenario1',
            source='https://greenwave_tests.example.com',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
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
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_incomplete_result():
    answers = [
        TestResultIncomplete(
            subject=test_subject(),
            test_case_name='test1',
            source='https://greenwave_tests.example.com',
            result_id=99,
            data={'scenario': 'scenario1'},
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
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
        result_id=99,
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_errored_result():
    answers = [
        TestResultErrored(
            subject=test_subject(),
            test_case_name='test1',
            source='https://greenwave_tests.example.com',
            result_id=99,
            data={'scenario': 'scenario1'},
            error_reason='Failed',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
        )
    ]
    waived = waive_answers(answers, waivers)
    expected_json = dict(
        type='test-result-errored-waived',
        testcase='test1',
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        result_id=99,
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
        error_reason='Failed',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_invalid_gatin_yaml():
    answers = [
        InvalidRemoteRuleYaml(
            subject=test_subject(),
            test_case_name='invalid-gating-yaml',
            source='https://greenwave_tests.example.com',
            details='',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='invalid-gating-yaml',
        )
    ]
    waived = waive_answers(answers, waivers)
    assert [] == waived


def test_waive_scenario():
    answers = [
        TestResultFailed(
            subject=test_subject(),
            test_case_name='test1',
            source='https://greenwave_tests.example.com',
            result_id=99,
            data={'scenario': 'scenario1'},
        )
    ]

    waivers = [
        dict(
            id=8,
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
            scenario='scenario2'
        )
    ]
    waived = waive_answers(answers, waivers)
    assert answers == waived

    waivers = [
        dict(
            id=9,
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
            scenario='scenario1'
        )
    ]
    waived = waive_answers(answers, waivers)
    expected_json = dict(
        type='test-result-failed-waived',
        testcase='test1',
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        result_id=99,
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()


def test_waive_scenarios_all():
    answers = [
        TestResultFailed(
            subject=test_subject(),
            test_case_name='test1',
            source='https://greenwave_tests.example.com',
            result_id=98,
            data={'scenario': 'scenario1'},
        ),
        TestResultFailed(
            subject=test_subject(),
            test_case_name='test1',
            source='https://greenwave_tests.example.com',
            result_id=99,
            data={'scenario': 'scenario2'},
        )
    ]

    waivers = [
        dict(
            id=9,
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            product_version='rawhide',
            testcase='test1',
            scenario=None
        )
    ]
    waived = waive_answers(answers, waivers)
    expected_json = [
        dict(
            type='test-result-failed-waived',
            testcase='test1',
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            result_id=98,
            waiver_id=9,
            scenario='scenario1',
            source='https://greenwave_tests.example.com',
        ),
        dict(
            type='test-result-failed-waived',
            testcase='test1',
            subject_type='koji_build',
            subject_identifier='nethack-1.2.3-1.rawhide',
            result_id=99,
            waiver_id=9,
            scenario='scenario2',
            source='https://greenwave_tests.example.com',
        ),
    ]
    assert expected_json == [w.to_json() for w in waived]


def test_waive_with_subject_type_alias():
    subject = test_subject()
    subject.subject_type.aliases = ['brew-build']
    answers = [
        TestResultMissing(
            subject=subject,
            test_case_name='test1',
            scenario='scenario1',
            source='https://greenwave_tests.example.com',
        )
    ]

    waived = waive_answers(answers, [])
    assert answers == waived

    waivers = [
        dict(
            id=9,
            subject_type='brew-build',
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
        waiver_id=9,
        scenario='scenario1',
        source='https://greenwave_tests.example.com',
    )
    assert 1 == len(waived)
    assert expected_json == waived[0].to_json()
