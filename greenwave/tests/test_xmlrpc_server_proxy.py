# SPDX-License-Identifier: GPL-2.0+

from unittest import mock

import pytest

from greenwave import xmlrpc_server_proxy


@pytest.mark.parametrize(
    "url, expected_transport, timeout, expected_timeout",
    (
        ("http://localhost:5000/api", xmlrpc_server_proxy.Transport, 15, 15),
        ("https://localhost:5000/api", xmlrpc_server_proxy.SafeTransport, 15, 15),
        ("https://localhost:5000/api", xmlrpc_server_proxy.SafeTransport, (3, 12), 12),
    ),
)
@mock.patch("greenwave.xmlrpc_server_proxy.Transport")
@mock.patch("greenwave.xmlrpc_server_proxy.SafeTransport")
def test_get_server_proxy(
    mock_safe_transport,
    mock_transport,
    url,
    expected_transport,
    timeout,
    expected_timeout,
):
    xmlrpc_server_proxy.get_server_proxy(url, timeout)

    if expected_transport == xmlrpc_server_proxy.Transport:
        mock_transport.__init__.assert_called_once_with(url, expected_timeout)
        mock_safe_transport.__init__.assert_not_called()
    elif expected_transport == xmlrpc_server_proxy.SafeTransport:
        mock_safe_transport.__init__.assert_called_once_with(url, expected_timeout)
        mock_transport.__init__.assert_not_called()
