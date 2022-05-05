# SPDX-License-Identifier: GPL-2.0+

# For an up-to-date version of this module, see:
#   https://pagure.io/monitor-flask-sqlalchemy

import os
import tempfile

from flask import Blueprint, Response
from prometheus_client import (  # noqa: F401
    ProcessCollector, CollectorRegistry, Counter, multiprocess,
    Histogram, generate_latest, start_http_server, CONTENT_TYPE_LATEST)

# Service-specific imports


if not os.environ.get('prometheus_multiproc_dir'):
    os.environ.setdefault('prometheus_multiproc_dir', tempfile.mkdtemp())
registry = CollectorRegistry()
ProcessCollector(registry=registry)
multiprocess.MultiProcessCollector(registry)
if os.getenv('MONITOR_STANDALONE_METRICS_SERVER_ENABLE', 'false') == 'true':
    port = os.getenv('MONITOR_STANDALONE_METRICS_SERVER_PORT', '10040')
    start_http_server(int(port), registry=registry)


# Generic metrics
messaging_rx_counter = Counter(
    'messaging_rx',
    'Total number of messages received',
    labelnames=['handler'],
    registry=registry)
messaging_rx_ignored_counter = Counter(
    'messaging_rx_ignored',
    'Number of received messages, which were ignored',
    labelnames=['handler'],
    registry=registry)
messaging_rx_processed_ok_counter = Counter(
    'messaging_rx_processed_ok',
    'Number of received messages, which were processed successfully',
    labelnames=['handler'],
    registry=registry)
messaging_rx_failed_counter = Counter(
    'messaging_rx_failed',
    'Number of received messages, which failed during processing',
    labelnames=['handler'],
    registry=registry)

messaging_tx_to_send_counter = Counter(
    'messaging_tx_to_send',
    'Total number of messages to send',
    labelnames=['handler'],
    registry=registry)
messaging_tx_stopped_counter = Counter(
    'messaging_tx_stopped',
    'Number of messages, which were eventually stopped before sending',
    labelnames=['handler'],
    registry=registry)
messaging_tx_sent_ok_counter = Counter(
    'messaging_tx_sent_ok',
    'Number of messages, which were sent successfully',
    labelnames=['handler'],
    registry=registry)
messaging_tx_failed_counter = Counter(
    'messaging_tx_failed',
    'Number of messages, for which the sender failed',
    labelnames=['handler'],
    registry=registry)

# Service-specific metrics
# https://github.com/prometheus/client_python/issues/210
# pylint: disable-msg=unexpected-keyword-arg,no-value-for-parameter
decision_exception_counter = Counter(
    'total_decision_exceptions',
    'All exceptions occurred in Greenwave "decision" API',
    registry=registry)
decision_request_duration_seconds = Histogram(
    'decision_request_duration_seconds',
    'Decision latency',
    registry=registry)
publish_decision_exceptions_waiver_counter = Counter(
    'publish_decision_exceptions_new_waiver',
    'All exceptions occurred in publishing a message after a new waiver',
    registry=registry)
publish_decision_exceptions_result_counter = Counter(
    'publish_decision_exceptions_new_result',
    'All exceptions occurred in publishing a message after a new result',
    registry=registry)


monitor_api = Blueprint(
    'monitor', __name__,
    url_prefix='')


@monitor_api.route('/metrics')
def metrics():
    return Response(generate_latest(registry),
                    content_type=CONTENT_TYPE_LATEST)
