# SPDX-License-Identifier: GPL-2.0+

policies = {
    # Mimic the default Errata rule used for RHEL-7 https://errata.devel.redhat.com/workflow_rules/1
    # In Errata, in order to transition to QE state, an advisory must complete rpmdiff test.
    # A completed rpmdiff test could be some dist.rpmdiff.* testcases in ResultsDB and all the
    # tests need to be passed.
    '1': {
        'product_version': 'rhel-7',
        'decision_context': 'errata_newfile_to_qe',
        'rules': [
            'dist.rpmdiff.comparison.xml_validity',
            'dist.rpmdiff.comparison.virus_scan',
            'dist.rpmdiff.comparison.upstream_source',
            'dist.rpmdiff.comparison.symlinks',
            'dist.rpmdiff.comparison.binary_stripping']
    }
}
