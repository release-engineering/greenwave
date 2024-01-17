# SPDX-License-Identifier: GPL-2.0+

import re
import socket
from requests.exceptions import ConnectionError

import pytest
from werkzeug.exceptions import BadGateway, NotFound

from greenwave.resources import (
    NoSourceException,
    KojiScmUrlParseError,
    retrieve_scm_from_koji,
    retrieve_yaml_remote_rule,
)


def test_retrieve_scm_from_rpm_build(app, koji_proxy):
    nvr = 'nethack-3.6.1-3.fc29'
    koji_proxy.getBuild.return_value = {
        'nvr': nvr,
        'extra': {
            'source': {
                'original_url': 'git+https://src.fedoraproject.org/rpms/nethack.git#master'
            }
        },
        'source': 'git+https://src.fedoraproject.org/rpms/nethack.git#'
                  '0c1a84e0e8a152897003bd7e27b3f407ff6ba040'
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji(nvr)
    assert namespace == 'rpms'
    assert rev == '0c1a84e0e8a152897003bd7e27b3f407ff6ba040'
    assert pkg_name == 'nethack'


def test_retrieve_scm_from_rpm_build_fallback_to_source(app, koji_proxy):
    nvr = 'nethack-3.6.1-3.fc29'
    koji_proxy.getBuild.return_value = {
        'nvr': nvr,
        'source': 'git+https://src.fedoraproject.org/rpms/nethack.git#'
                  '0c1a84e0e8a152897003bd7e27b3f407ff6ba040'
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji(nvr)
    assert namespace == 'rpms'
    assert rev == '0c1a84e0e8a152897003bd7e27b3f407ff6ba040'
    assert pkg_name == 'nethack'


def test_retrieve_scm_from_container_build(app, koji_proxy):
    nvr = 'golang-github-openshift-prometheus-alert-buffer-container-v3.10.0-0.34.0.0'
    koji_proxy.getBuild.return_value = {
        'nvr': nvr,
        'source': 'git://pkgs.devel.redhat.com/containers/'
                  'golang-github-openshift-prometheus-alert-buffer#'
                  '46af2f8efbfb0a4e7e7d5676f4efb997f72d4b8c'
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji(nvr)
    assert namespace == 'containers'
    assert rev == '46af2f8efbfb0a4e7e7d5676f4efb997f72d4b8c'
    assert pkg_name == 'golang-github-openshift-prometheus-alert-buffer'


def test_retrieve_scm_from_nonexistent_build(app, koji_proxy):
    nvr = 'foo-1.2.3-1.fc29'
    koji_proxy.getBuild.return_value = {}
    expected_error = 'Failed to find Koji build for "{}" at "{}"'.format(
        nvr, app.config["KOJI_BASE_URL"]
    )
    with pytest.raises(NotFound, match=expected_error):
        retrieve_scm_from_koji(nvr)


def test_retrieve_scm_from_build_with_missing_source(app, koji_proxy):
    nvr = "foo-1.2.3-1.fc29"
    koji_proxy.getBuild.return_value = {"nvr": nvr}
    expected_error = 'expected SCM URL in "source" attribute'
    with pytest.raises(NoSourceException, match=expected_error):
        retrieve_scm_from_koji(nvr)


def test_retrieve_scm_from_build_without_namespace(app, koji_proxy):
    nvr = 'foo-1.2.3-1.fc29'
    koji_proxy.getBuild.return_value = {
        'nvr': nvr,
        'extra': {
            'source': {
                'original_url': 'git+https://src.fedoraproject.org/foo.git#deadbeef'
            }
        }
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji(nvr)
    assert namespace == ''
    assert rev == 'deadbeef'
    assert pkg_name == 'foo'


def test_retrieve_scm_from_koji_build_not_found(app, koji_proxy):
    nvr = 'foo-1.2.3-1.fc29'
    expected_error = '404 Not Found: Failed to find Koji build for "{}" at "{}"'.format(
        nvr, app.config['KOJI_BASE_URL']
    )
    koji_proxy.getBuild.return_value = {}
    with pytest.raises(NotFound, match=expected_error):
        retrieve_scm_from_koji(nvr)


def test_retrieve_scm_from_build_with_missing_rev(app, koji_proxy):
    nvr = 'foo-1.2.3-1.fc29'
    koji_proxy.getBuild.return_value = {
        'nvr': nvr,
        'extra': {
            'source': {
                'original_url': 'git+https://src.fedoraproject.org/rpms/foo.git'
            }
        }
    }
    expected_error = 'missing URL fragment with SCM revision information'
    with pytest.raises(KojiScmUrlParseError, match=expected_error):
        retrieve_scm_from_koji(nvr)


def test_retrieve_yaml_remote_rule_no_namespace(app, requests_mock):
    requests_mock.head(
        'https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml', status_code=404)
    # Return 404, because we are only interested in the URL in the request
    # and whether it is correct even with empty namespace.
    returned_file = retrieve_yaml_remote_rule(
        app.config['REMOTE_RULE_POLICIES']['*'].format(
            rev='deadbeaf', pkg_name='pkg', pkg_namespace=''
        )
    )

    request_history = [(r.method, r.url) for r in requests_mock.request_history]
    assert request_history == [(
        'HEAD', 'https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml'
    )]
    assert returned_file is None


def test_retrieve_yaml_remote_rule_connection_error(app, requests_mock):
    requests_mock.head('https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml')
    exc = ConnectionError('Something went terribly wrong...')
    requests_mock.get('https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml', exc=exc)

    expected_error = re.escape(
        'Got unexpected status code 502 for'
        ' https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml:'
        ' {"message": "Something went terribly wrong..."}'
    )
    with pytest.raises(BadGateway, match=expected_error):
        retrieve_yaml_remote_rule(
            app.config['REMOTE_RULE_POLICIES']['*'].format(
                rev='deadbeaf', pkg_name='pkg', pkg_namespace=''
            )
        )


def test_retrieve_scm_from_koji_build_socket_error(app, koji_proxy):
    koji_proxy.getBuild.side_effect = socket.error('Socket is closed')
    nvr = 'nethack-3.6.1-3.fc29'
    expected_error = 'Could not reach Koji: Socket is closed'
    with pytest.raises(socket.error, match=expected_error):
        retrieve_scm_from_koji(nvr)
