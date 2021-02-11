# SPDX-License-Identifier: GPL-2.0+


def _is_waived(answer, waivers):
    """
    Returns true only if there is a matching waiver for given answer.
    """
    return any(
        waiver['subject_type'] == answer.subject.type and
        waiver['subject_identifier'] == answer.subject.identifier and
        waiver['testcase'] == answer.test_case_name and
        (not waiver.get('scenario') or waiver['scenario'] == answer.scenario)
        for waiver in waivers
    )


def _maybe_waive(answer, waivers):
    """
    Returns waived answer if it's unsatisfied there is a matching waiver,
    otherwise returns unchanged answer.
    """
    if not answer.is_satisfied and _is_waived(answer, waivers):
        return answer.to_waived()
    return answer


def waive_answers(answers, waivers):
    """
    Returns answers with unsatisfied answers waived
    (`RuleNotSatisfied.to_waived()`) if there is a matching waiver.
    """
    waived_answers = [_maybe_waive(answer, waivers) for answer in answers]
    waived_answers = [answer for answer in waived_answers if answer is not None]
    return waived_answers
