# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Provides an "xmlrpc.client.ServerProxy" object with a timeout on the socket.
"""
import urllib.parse
import xmlrpc.client

from flask import current_app, has_app_context


def get_server_proxy(uri, timeout=None):
    """
    Create an :py:class:`xmlrpc.client.ServerProxy` instance with a socket timeout.

    This is a workaround for https://bugs.python.org/issue14134.

    Args:
        uri (str): The connection point on the server in the format of scheme://host/target.
        timeout (int): The timeout to set on the transport socket. This defaults to the Flask
            configuration `REQUESTS_TIMEOUT` if there is an application context.

    Returns:
        xmlrpc.client.ServerProxy: An instance of :py:class:`xmlrpc.client.ServerProxy` with
            a socket timeout set.
    """
    if timeout is None and has_app_context():
        if isinstance(current_app.config['REQUESTS_TIMEOUT'], tuple):
            timeout = current_app.config['REQUESTS_TIMEOUT'][1]
        else:
            timeout = current_app.config['REQUESTS_TIMEOUT']

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

    def make_connection(self, *args, **kwargs):  # pragma: no cover
        connection = super().make_connection(*args, **kwargs)
        connection.timeout = self._timeout
        return connection


class SafeTransport(xmlrpc.client.SafeTransport):
    def __init__(self, *args, timeout=None, **kwargs):  # pragma: no cover
        super().__init__(*args, **kwargs)
        self._timeout = timeout

    def make_connection(self, *args, **kwargs):  # pragma: no cover
        connection = super().make_connection(*args, **kwargs)
        connection.timeout = self._timeout
        return connection
