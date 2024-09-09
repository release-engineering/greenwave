# SPDX-License-Identifier: GPL-2.0+
"""
Provides an "xmlrpc_client.ServerProxy" object with a timeout on the socket.
"""

import logging

from defusedxml.xmlrpc import xmlrpc_client
from opentelemetry import trace

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def get_server_proxy(uri, *, timeout, retry) -> xmlrpc_client.ServerProxy:
    """
    Create an :py:class:`xmlrpc_client.ServerProxy` instance with a socket timeout.

    This is a workaround for https://bugs.python.org/issue14134.

    Args:
        uri (str): The connection point on the server in the format of scheme://host/target.
        timeout (int): The timeout to set on the transport socket.

    Returns:
        xmlrpc_client.ServerProxy: An instance of :py:class:`xmlrpc_client.ServerProxy` with
            a socket timeout set.
    """
    transport = SafeTransport(timeout=timeout, retry=retry)
    return xmlrpc_client.ServerProxy(uri, transport=transport, allow_none=True)


class SafeTransport(xmlrpc_client.SafeTransport):
    def __init__(self, *args, timeout=None, retry=3, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout
        self._retry = retry

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self._timeout
        return connection

    @tracer.start_as_current_span("request")
    def request(self, *args, **kwargs):
        for attempt in range(1, self._retry + 1):
            try:
                return super().request(*args, **kwargs)
            except TimeoutError:
                log.warning("Retrying on XMLRPC timeout (attempt=%s)", attempt)

        return super().request(*args, **kwargs)
