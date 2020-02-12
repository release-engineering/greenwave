# SPDX-License-Identifier: GPL-2.0+

import mock

from textwrap import dedent
from greenwave.app_factory import create_app
from greenwave.policies import Policy
from greenwave.config import TestingConfig


@mock.patch('greenwave.policies.load_policies')
def test_remote_rules_base_url(mock_load_policies):
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
    config.DIST_GIT_BASE_URL = 'http://localhost.localdomain/'
    config.DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}{other_params}/blablabla/gating.yaml'
    config.REMOTE_RULE_POLICIES = {}

    app = create_app(config)

    assert app.config['DIST_GIT_URL_TEMPLATE'] == (
        'http://localhost.localdomain/{other_params}/blablabla/gating.yaml'
    )
