# SPDX-License-Identifier: GPL-2.0+

# For an up-to-date version of this module, see:
#   https://pagure.io/monitor-flask-sqlalchemy

import os
from dataclasses import dataclass, field
from functools import lru_cache, wraps

from statsd import StatsClient


# Note: StatsClient instances are thread-safe.
@lru_cache
def stats_client():
    statsd_url = os.environ.get('GREENWAVE_STATSD_HOST')
    if statsd_url:
        server, port = statsd_url.split(':')
        return StatsClient(server, int(port))

    return None


@dataclass
class Stat:
    name: str
    labeldict: dict[str, str] = field(default_factory=dict)

    def __str__(self):
        if not self.labeldict:
            return self.name

        labels = ','.join(
            f'{name}={value}'
            for name, value in self.labeldict.items()
        )
        return f'{self.name}[{labels}]'


class Counter(Stat):
    def inc(self):
        client = stats_client()
        if client:
            client.incr(str(self))

    def labels(self, **labeldict):
        return Counter(self.name, labeldict=labeldict)

    def count_exceptions(self):
        """Returns function decorator to increase counter on exception."""
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except BaseException:
                    self.inc()
                    raise
            return wrapper
        return decorator


class Histogram(Stat):
    def time(self):
        """Returns function decorator to that sends recorder call time."""
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                client = stats_client()
                if client:
                    with client.timer(str(self)):
                        return fn(*args, **kwargs)
                return fn(*args)
            return wrapper
        return decorator


# Total number of messages received
messaging_rx_counter = Counter('messaging_rx')
# Number of received messages, which were ignored
messaging_rx_ignored_counter = Counter('messaging_rx_ignored')
# Number of received messages, which were processed successfully
messaging_rx_processed_ok_counter = Counter('messaging_rx_processed_ok')
# Number of received messages, which failed during processing
messaging_rx_failed_counter = Counter('messaging_rx_failed')

# Total number of messages to send
messaging_tx_to_send_counter = Counter('messaging_tx_to_send')
# Number of messages, which were eventually stopped before sending
messaging_tx_stopped_counter = Counter('messaging_tx_stopped')
# Number of messages, which were sent successfully
messaging_tx_sent_ok_counter = Counter('messaging_tx_sent_ok')
# Number of messages, for which the sender failed
messaging_tx_failed_counter = Counter('messaging_tx_failed')

# All exceptions occurred in Greenwave "decision" API
decision_exception_counter = Counter('total_decision_exceptions')
# Decision latency
decision_request_duration_seconds = Histogram('decision_request_duration_seconds')
# All exceptions occurred in publishing a message after a new waiver
publish_decision_exceptions_waiver_counter = Counter('publish_decision_exceptions_new_waiver')
# All exceptions occurred in publishing a message after a new result
publish_decision_exceptions_result_counter = Counter('publish_decision_exceptions_new_result')
