# SPDX-License-Identifier: GPL-2.0+

import socket

import pytest

from greenwave import product_versions


@pytest.mark.parametrize('brew_pv, expected_pv', (
    ('rawhide', 'fedora-rawhide'),
    ('f35-candidate', 'fedora-35'),
    ('epel7-candidate', 'epel-7'),
    ('rhel-8.5.0-candidate', 'rhel-8'),
    ('rhel-9.0.0-beta-candidate', 'rhel-9'),
))
def test_guess_koji_build_product_version(brew_pv, expected_pv, koji_proxy, app):
    koji_proxy.getTaskRequest.return_value = [
        'git://pkgs.devel.example.com/rpms/nethack#12345abcde',
        brew_pv,
        {'scratch': False}]
    pv = product_versions._guess_koji_build_product_version(
        brew_pv, 'http://localhost:5006/kojihub', koji_task_id=1)
    assert pv == expected_pv


@pytest.mark.parametrize('task_id', (None, 3))
def test_guess_koji_build_product_version_socket_error(task_id, koji_proxy, app):
    subject_identifier = 'release-e2e-test-1.0.1685-1.el5'
    koji_proxy.getBuild.side_effect = koji_proxy.getTaskRequest.side_effect = (
        socket.timeout('timed out')
    )
    expected = 'Could not reach Koji: timed out'
    with pytest.raises(ConnectionError, match=expected):
        # pylint: disable=protected-access
        product_versions._guess_koji_build_product_version(
            subject_identifier, 'http://localhost:5006/kojihub', task_id)
