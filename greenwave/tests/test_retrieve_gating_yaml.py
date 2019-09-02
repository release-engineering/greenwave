# SPDX-License-Identifier: GPL-2.0+

import socket

import pytest
import mock
from werkzeug.exceptions import BadGateway

import greenwave.app_factory
from greenwave.resources import (
    retrieve_scm_from_koji_build, retrieve_yaml_remote_rule, retrieve_scm_from_koji)

KOJI_URL = 'https://koji.fedoraproject.org/kojihub'


def test_retrieve_scm_from_rpm_build():
    nvr = 'nethack-3.6.1-3.fc29'
    build = {
        'nvr': nvr,
        'source': 'git+https://src.fedoraproject.org/rpms/nethack.git#0c1a84e0e8a152897003bd7e27b3f407ff6ba040' # noqa
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji_build(nvr, build, KOJI_URL)
    assert namespace == 'rpms'
    assert rev == '0c1a84e0e8a152897003bd7e27b3f407ff6ba040'
    assert pkg_name == 'nethack'


def test_retrieve_scm_from_container_build():
    nvr = 'golang-github-openshift-prometheus-alert-buffer-container-v3.10.0-0.34.0.0'
    build = {
        'nvr': nvr,
        'source': 'git://pkgs.devel.redhat.com/containers/golang-github-openshift-prometheus-alert-buffer#46af2f8efbfb0a4e7e7d5676f4efb997f72d4b8c' # noqa
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji_build(nvr, build, KOJI_URL)
    assert namespace == 'containers'
    assert rev == '46af2f8efbfb0a4e7e7d5676f4efb997f72d4b8c'
    assert pkg_name == 'golang-github-openshift-prometheus-alert-buffer'


def test_retrieve_scm_from_nonexistent_build():
    nvr = 'foo-1.2.3-1.fc29'
    build = {}
    expected_error = 'Failed to find Koji build for "{}" at "{}"'.format(nvr, KOJI_URL)
    with pytest.raises(BadGateway, match=expected_error):
        retrieve_scm_from_koji_build(nvr, build, KOJI_URL)


def test_retrieve_scm_from_build_with_missing_source():
    nvr = 'foo-1.2.3-1.fc29'
    build = {
        'nvr': nvr
    }
    expected_error = 'expected SCM URL in "source" attribute'
    with pytest.raises(BadGateway, match=expected_error):
        retrieve_scm_from_koji_build(nvr, build, KOJI_URL)


def test_retrieve_scm_from_build_without_namespace():
    nvr = 'foo-1.2.3-1.fc29'
    build = {
        'nvr': nvr,
        'source': 'git+https://src.fedoraproject.org/foo.git#deadbeef',
    }
    namespace, pkg_name, rev = retrieve_scm_from_koji_build(nvr, build, KOJI_URL)
    assert namespace == ''
    assert rev == 'deadbeef'
    assert pkg_name == 'foo'


def test_retrieve_scm_from_build_with_missing_rev():
    nvr = 'foo-1.2.3-1.fc29'
    build = {
        'nvr': nvr,
        'source': 'git+https://src.fedoraproject.org/rpms/foo.git',
    }
    expected_error = 'missing URL fragment with SCM revision information'
    with pytest.raises(BadGateway, match=expected_error):
        retrieve_scm_from_koji_build(nvr, build, KOJI_URL)


def test_retrieve_yaml_remote_rule_no_namespace():
    app = greenwave.app_factory.create_app()
    with app.app_context():
        with mock.patch('greenwave.resources.requests_session') as session:
            # Return 404, because we are only interested in the URL in the request
            # and whether it is correct even with empty namespace.
            response = mock.MagicMock()
            response.status_code = 404
            session.request.return_value = response
            retrieve_yaml_remote_rule("deadbeaf", "pkg", "")

            expected_call = mock.call(
                'HEAD',
                'https://src.fedoraproject.org/pkg/raw/deadbeaf/f/gating.yaml',
                headers={'Content-Type': 'application/json'}, timeout=60)
            assert session.request.mock_calls == [expected_call]


@mock.patch('greenwave.resources.xmlrpc.client.ServerProxy')
def test_retrieve_scm_from_koji_build_socket_error(mock_xmlrpc_client):
    mock_auth_server = mock_xmlrpc_client.return_value
    mock_auth_server.getBuild.side_effect = socket.error('Socket is closed')
    app = greenwave.app_factory.create_app()
    nvr = 'nethack-3.6.1-3.fc29'
    expected_error = 'Could not reach Koji: Socket is closed'
    with pytest.raises(socket.error, match=expected_error):
        with app.app_context():
            retrieve_scm_from_koji(nvr)
