# SPDX-License-Identifier: GPL-2.0+

import mock
import pytest

from textwrap import dedent

from greenwave.app_factory import create_app
from greenwave.policies import Policy
from greenwave.config import TestingConfig


@mock.patch('greenwave.policies.load_policies')
def test_remote_rules_misconfigured(mock_load_policies):
    """
    The application shouldn't start if RemoteRule is in policy configuration
    but if cannot be used because dist-git or koji URL is not configured.
    """

    policies = Policy.safe_load_all(dedent("""
        --- !Policy
        id: test_policy
        product_versions: [fedora-rawhide]
        decision_context: another_test_context
        subject_type: koji_build
        rules:
          - !RemoteRule {}
    """))
    mock_load_policies.return_value = policies

    config = TestingConfig()
    config.DIST_GIT_BASE_URL = ''

    expected_error = 'If you want to apply a RemoteRule you need to configure'

    with pytest.raises(RuntimeError, match=expected_error):
        create_app(config)
