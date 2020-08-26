# SPDX-License-Identifier: GPL-2.0+

import socket

import mock
import pytest

from greenwave import product_versions


@pytest.mark.parametrize('task_id', (None, 3))
def test_guess_koji_build_product_version_socket_error(task_id):
    subject_identifier = 'release-e2e-test-1.0.1685-1.el5'
    mock_proxy = mock.Mock()
    mock_proxy.getBuild.side_effect = mock_proxy.getTaskRequest.side_effect = (
        socket.timeout('timed out')
    )
    expected = 'Could not reach Koji: timed out'
    with pytest.raises(ConnectionError, match=expected):
        # pylint: disable=protected-access
        product_versions._guess_koji_build_product_version(subject_identifier, mock_proxy, task_id)
