
# SPDX-License-Identifier: GPL-2.0+

from greenwave.app_factory import create_app
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


def test_load_policies():
    app = create_app('greenwave.config.TestingConfig')
    assert len(app.config['policies']) > 0
    assert app.config['policies'][0].id == '1'
    assert app.config['policies'][0].product_versions == ['rhel-7']
    assert app.config['policies'][0].decision_context == 'errata_newfile_to_qe'
    rule = app.config['policies'][0].rules[0]
    assert rule.test_case_name == 'dist.rpmdiff.analysis.abi_symbols'