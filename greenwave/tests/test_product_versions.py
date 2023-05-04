# SPDX-License-Identifier: GPL-2.0+

import socket

import pytest

from greenwave import product_versions
from greenwave.subjects.factory import create_subject


def mock_subject():
    return create_subject('koji_build', 'nethack-1.2.3-1.rawhide')


@pytest.mark.parametrize('brew_pv, expected_pvs', (
    ('rawhide', ['fedora-rawhide']),
    ('f35-candidate', ['fedora-35']),
    ('epel7-candidate', ['epel-7']),
    ('rhel-8.5.0-candidate', ['rhel-8', 'rhel-8.5']),
    ('rhel-9.2.0-beta-candidate', ['rhel-9', 'rhel-9.2']),
))
def test_guess_koji_build_product_version(brew_pv, expected_pvs, koji_proxy, app):
    koji_proxy.getTaskRequest.return_value = [
        'git://pkgs.devel.example.com/rpms/nethack#12345abcde',
        brew_pv,
        {'scratch': False}]
    pvs = product_versions._guess_koji_build_product_versions(
        mock_subject(), 'http://localhost:5006/kojihub', koji_task_id=1)
    assert pvs == expected_pvs


@pytest.mark.parametrize('task_id', (None, 3))
def test_guess_koji_build_product_version_socket_error(task_id, koji_proxy, app):
    koji_proxy.getBuild.side_effect = koji_proxy.getTaskRequest.side_effect = (
        socket.timeout('timed out')
    )
    expected = 'Could not reach Koji: timed out'
    with pytest.raises(ConnectionError, match=expected):
        # pylint: disable=protected-access
        product_versions._guess_koji_build_product_versions(
            mock_subject(), 'http://localhost:5006/kojihub', task_id)
