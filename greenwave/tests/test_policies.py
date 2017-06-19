
# SPDX-License-Identifier: GPL-2.0+

from greenwave.policies import summarize_answers, RuleSatisfied, TestResultMissing, TestResultFailed


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()]) == \
        'all required tests passed'
    assert summarize_answers([TestResultFailed('item', 'test', 'id'), RuleSatisfied()]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test')]) == \
        'no test results found'
    assert summarize_answers([TestResultMissing('item', 'test'),
                              TestResultFailed('item', 'test', 'id')]) == \
        '1 of 2 required tests failed'
    assert summarize_answers([TestResultMissing('item', 'test'), RuleSatisfied()]) == \
        '1 of 2 required tests not found'
