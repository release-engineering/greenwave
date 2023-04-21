# SPDX-License-Identifier: GPL-2.0+


def _find_waived_id(answer, waivers):
    """
    Returns waiver ID of a matching waiver for given answer otherwise None.
    """
    for waiver in waivers:
        if (
            waiver["subject_type"] == answer.subject.type
            and waiver["subject_identifier"] == answer.subject.identifier
            and waiver["testcase"] == answer.test_case_name
            and (not waiver.get("scenario") or waiver["scenario"] == answer.scenario)
        ):
            return waiver["id"]
    return None


def _maybe_waive(answer, waivers):
    """
    Returns waived answer if it's unsatisfied there is a matching waiver,
    otherwise returns unchanged answer.
    """
    if not answer.is_satisfied:
        waiver_id = _find_waived_id(answer, waivers)
        if waiver_id is not None:
            return answer.to_waived(waiver_id)
    return answer


def waive_answers(answers, waivers):
    """
    Returns answers with unsatisfied answers waived
    (`RuleNotSatisfied.to_waived()`) if there is a matching waiver.
    """
    waived_answers = [_maybe_waive(answer, waivers) for answer in answers]
    waived_answers = [answer for answer in waived_answers if answer is not None]
    return waived_answers
