# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Provides an "xmlrpc.client.ServerProxy" object with a timeout on the socket.
"""
import http.client
import logging
import urllib.parse
import xmlrpc.client
from functools import lru_cache
from time import sleep

log = logging.getLogger(__name__)

RETRY_ON_EXCEPTIONS = (
    http.client.CannotSendRequest,
    http.client.ResponseNotReady,
)
MAX_RETRIES = 3


class XmlRpcServerProxy:
    def __init__(self, uri, timeout):
        self.uri = uri
        self.timeout = timeout
        self.reconnect()

    def reconnect(self):
        parsed_uri = urllib.parse.urlparse(self.uri)
        if parsed_uri.scheme == 'https':
            transport = SafeTransport(timeout=self.timeout)
        else:
            transport = Transport(timeout=self.timeout)

        self.proxy = xmlrpc.client.ServerProxy(
            self.uri, transport=transport, allow_none=True)

    def __getattr__(self, name):
        return XmlRpcMethod(self, name)


class XmlRpcMethod:
    def __init__(self, proxy, name):
        self.proxy = proxy
        self.name = name

    def __call__(self, *args):
        retry_counter = 0
        while True:
            try:
                return getattr(self.proxy.proxy, self.name)(*args)
            except RETRY_ON_EXCEPTIONS as e:
                retry_counter += 1
                if retry_counter > MAX_RETRIES:
                    raise

                log.warning("Retrying XMLRPC call %r on error: %s", self.name, e)
                sleep(2 ** (retry_counter - 1))
                self.proxy.reconnect()


@lru_cache(maxsize=None)
def get_server_proxy(uri, timeout):
    """
    Create an :py:class:`xmlrpc.client.ServerProxy` instance with a socket timeout.

    This is a workaround for https://bugs.python.org/issue14134.

    Args:
        uri (str): The connection point on the server in the format of scheme://host/target.
        timeout (int): The timeout to set on the transport socket.

    Returns:
        XmlRpcServerProxy: Wrapper for :py:class:`xmlrpc.client.ServerProxy` with
            a socket timeout set.
    """
    return XmlRpcServerProxy(uri, timeout)


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
