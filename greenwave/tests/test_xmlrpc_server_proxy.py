# SPDX-License-Identifier: GPL-2.0+

from unittest import mock

from pytest import raises

from greenwave import xmlrpc_server_proxy


@mock.patch("greenwave.xmlrpc_server_proxy.SafeTransport.single_request")
def test_xmlrpc_retry(xmlrpc_single_request):
    xmlrpc_single_request.side_effect = TimeoutError
    proxy = xmlrpc_server_proxy.get_server_proxy(
        "https://localhost:5000/api", timeout=1, retry=1
    )
    with raises(TimeoutError):
        proxy.getBuild("TEST")
    assert len(xmlrpc_single_request.mock_calls) == 2
