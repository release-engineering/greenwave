# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Provides an "xmlrpc.client.ServerProxy" object with a timeout on the socket.
"""
import urllib.parse
import xmlrpc.client
from functools import lru_cache


@lru_cache(maxsize=None)
def get_server_proxy(uri, timeout):
    """
    Create an :py:class:`xmlrpc.client.ServerProxy` instance with a socket timeout.

    This is a workaround for https://bugs.python.org/issue14134.

    Args:
        uri (str): The connection point on the server in the format of scheme://host/target.
        timeout (int): The timeout to set on the transport socket.

    Returns:
        xmlrpc.client.ServerProxy: An instance of :py:class:`xmlrpc.client.ServerProxy` with
            a socket timeout set.
    """
    parsed_uri = urllib.parse.urlparse(uri)
    if parsed_uri.scheme == 'https':
        transport = SafeTransport(timeout=timeout)
    else:
        transport = Transport(timeout=timeout)

    return xmlrpc.client.ServerProxy(uri, transport=transport)


class Transport(xmlrpc.client.Transport):
    def __init__(self, *args, timeout=None, **kwargs):  # pragma: no cover
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):  # pragma: no cover
        connection = super().make_connection(host)
        connection.timeout = self._timeout
        return connection


class SafeTransport(xmlrpc.client.SafeTransport):
    def __init__(self, *args, timeout=None, **kwargs):  # pragma: no cover
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, host):  # pragma: no cover
        connection = super().make_connection(host)
        connection.timeout = self._timeout
        return connection
