
# SPDX-License-Identifier: GPL-2.0+

from greenwave.policies import summarize_answers, RuleSatisfied, TestResultMissing, TestResultFailed


def test_summarize_answers():
    assert summarize_answers([RuleSatisfied()], '1') == \
        'policy 1 is satisfied as all required tests are passing'
    assert summarize_answers([TestResultFailed('item', 'test', 'id'), RuleSatisfied()], '1') == \
        '1 of 2 required tests failed, the policy 1 is not satisfied'
    assert summarize_answers([TestResultMissing('item', 'test')], '1') == \
        'no test results found'
    assert summarize_answers([TestResultMissing('item', 'test'),
                              TestResultFailed('item', 'test', 'id')], '1') == \
        '1 of 2 required tests failed, the policy 1 is not satisfied'
    # XXX fix this one
    assert summarize_answers([TestResultMissing('item', 'test'), RuleSatisfied()], '1') == \
        'inexplicable result'
