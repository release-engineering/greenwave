# SPDX-License-Identifier: GPL-2.0+
import http.client
import uuid

import mock
import pytest

from greenwave import xmlrpc_server_proxy


def unique_koji_url(protocol='https'):
    """
    Generates unique Koji API URL to bypass caching on arguments in
    xmlrpc_server_proxy().
    """
    return f'{protocol}://koji-{uuid.uuid4()}.example.com/kojihub'


@pytest.fixture
def mock_xmlrpc_proxy():
    with mock.patch(
            'greenwave.xmlrpc_server_proxy.xmlrpc.client.ServerProxy') as proxy:
        yield proxy


def test_xmlrpc_server_proxy_call(mock_xmlrpc_proxy):
    proxy = xmlrpc_server_proxy.get_server_proxy(unique_koji_url(), timeout=0)
    assert mock_xmlrpc_proxy.call_count == 1
    proxy.getBuild('fake_koji_build')
    assert mock_xmlrpc_proxy.call_count == 1
    proxy.proxy.getBuild.assert_called_once_with('fake_koji_build')


def test_xmlrpc_server_proxy_failure(mock_xmlrpc_proxy):
    proxy = xmlrpc_server_proxy.get_server_proxy(unique_koji_url(), timeout=0)
    assert mock_xmlrpc_proxy.call_count == 1
    proxy.proxy.getBuild.side_effect = http.client.ResponseNotReady
    with mock.patch('greenwave.xmlrpc_server_proxy.sleep') as mock_sleep:
        with pytest.raises(http.client.ResponseNotReady):
            proxy.getBuild('fake_koji_build')
        mock_sleep.assert_has_calls([
            mock.call(1),
            mock.call(2),
            mock.call(4),
        ])
    assert mock_xmlrpc_proxy.call_count == 4
    proxy.proxy.getBuild.assert_has_calls([
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
    ])


def test_xmlrpc_server_proxy_reconnect(mock_xmlrpc_proxy):
    proxy = xmlrpc_server_proxy.get_server_proxy(unique_koji_url(), timeout=0)
    assert mock_xmlrpc_proxy.call_count == 1
    proxy.proxy.getBuild.side_effect = (
        http.client.ResponseNotReady,
        http.client.ResponseNotReady,
        http.client.ResponseNotReady,
        {},
    )
    with mock.patch('greenwave.xmlrpc_server_proxy.sleep') as mock_sleep:
        proxy.getBuild('fake_koji_build')
        mock_sleep.assert_has_calls([
            mock.call(1),
            mock.call(2),
            mock.call(4),
        ])
    assert mock_xmlrpc_proxy.call_count == 4
    proxy.proxy.getBuild.assert_has_calls([
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
        mock.call('fake_koji_build'),
    ])


@pytest.mark.parametrize(
    'url, expected_transport, timeout, expected_timeout',
    (
        (unique_koji_url('http'), xmlrpc_server_proxy.Transport, 15, 15),
        (unique_koji_url(), xmlrpc_server_proxy.SafeTransport, 15, 15),
        (unique_koji_url(), xmlrpc_server_proxy.SafeTransport, (3, 12), 12),
    ),
)
@mock.patch('greenwave.xmlrpc_server_proxy.Transport')
@mock.patch('greenwave.xmlrpc_server_proxy.SafeTransport')
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


def test_get_server_proxy_cached():
    """Server proxy objects are cached"""
    url1 = unique_koji_url()
    s1 = xmlrpc_server_proxy.get_server_proxy(url1, timeout=None)
    s2 = xmlrpc_server_proxy.get_server_proxy(url1, timeout=None)
    assert s1 is s2

    s3 = xmlrpc_server_proxy.get_server_proxy(url1, timeout=10)
    assert s1 is not s3

    url2 = unique_koji_url()
    s4 = xmlrpc_server_proxy.get_server_proxy(url2, timeout=None)
    assert s1 is not s4
