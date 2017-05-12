
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#

policies = {
    # Mimic the default Errata rule used for RHEL-7 https://errata.devel.redhat.com/workflow_rules/1
    # In Errata, in order to transition to QE state, an advisory must complete rpmdiff test.
    # A completed rpmdiff test could be some dist.rpmdiff.* testcases in ResultsDB and all the
    # tests need to be passed.
    '1': {
        'product_version': 'rhel-7',
        'decision_context': 'errta_newfile_to_qe',
        'rules': [
            'dist.rpmdiff.comparison.xml_validity',
            'dist.rpmdiff.comparison.virus_scan',
            'dist.rpmdiff.comparison.upstream_source',
            'dist.rpmdiff.comparison.symlinks',
            'dist.rpmdiff.comparison.binary_stripping']
    }
}
