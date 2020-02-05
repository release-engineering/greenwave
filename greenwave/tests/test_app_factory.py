# SPDX-License-Identifier: GPL-2.0+

import mock
import pytest

from textwrap import dedent

from greenwave.app_factory import create_app, _can_use_remote_rule
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
    config.DIST_GIT_URL_TEMPLATE = ''
    config.REMOTE_RULE_POLICIES = {}

    expected_error = 'If you want to apply a RemoteRule'

    with pytest.raises(RuntimeError, match=expected_error):
        create_app(config)


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


def test_can_use_remote_rule_http_fallback():
    """ Test that _can_use_remote_rule verifies the configuration properly if HTTP is used. """
    config = {
        'KOJI_BASE_URL': 'https://koji.domain.local/kojihub',
        'DIST_GIT_URL_TEMPLATE':
            'https://dist-git.domain.local/{pkg_namespace}{pkg_name}/raw/{rev}/f/gating.yaml'
    }
    assert _can_use_remote_rule(config) is True


def test_can_use_remote_rule_http():
    """ Test that _can_use_remote_rule verifies the configuration properly if HTTP is used. """
    config = {
        'KOJI_BASE_URL': 'https://koji.domain.local/kojihub',
        'REMOTE_RULE_POLICIES': {
            '*': {
                'HTTP_URL_TEMPLATE': 'https://src.fedoraproject.org/{pkg_namespace}{pkg_name}/'
                                     'raw/{rev}/f/gating.yaml'
            }
        }
    }
    assert _can_use_remote_rule(config) is True


@pytest.mark.parametrize('config', (
    {
        'REMOTE_RULE_POLICIES': {
            'brew-build-group': {
                'GIT_URL': 'git@gitlab.cee.redhat.com:devops/greenwave-policies/side-tags.git',
                'GIT_PATH_TEMPLATE': '{pkg_namespace}/{pkg_name}.yaml'
            }
        },
    },
    {
        'KOJI_BASE_URL': 'https://koji.domain.local/kojihub'
    }
))
def test_can_use_remote_rule_missing_config(config):
    """ Test that _can_use_remote_rule will return False if a configuration is missing. """
    assert _can_use_remote_rule(config) is False
