# SPDX-License-Identifier: GPL-2.0+

import os
from prometheus_client import Counter, Histogram, multiprocess, CollectorRegistry


# tmp dir for Prometheus monitoring registry.
# Putting this here and not in the "create_app" function, because "create_app" imports the api
# ...so the check for this env variable would be made before the "create_app" can be able to set it
# This is executed only once at server starting, so it is not so bad for performace.
if not os.environ.get('prometheus_multiproc_dir'):
    os.environ.setdefault('prometheus_multiproc_dir', '/tmp')
registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)
# https://github.com/prometheus/client_python/issues/210
# pylint: disable-msg=unexpected-keyword-arg,no-value-for-parameter
decision_exception_counter = Counter('total_decision_exceptions', ('All exceptions occurred in '
                                                                   'Greenwave "decision" API'),
                                     registry=registry)
decision_request_duration_seconds = Histogram('decision_request_duration_seconds',
                                              'Decision latency',
                                              registry=registry)
publish_decision_exceptions_waiver_counter = Counter('publish_decision_exceptions_new_waiver',
                                                     ('All exceptions occurred in publishing a '
                                                      'message after a new waiver'),
                                                     registry=registry)
publish_decision_exceptions_result_counter = Counter('publish_decision_exceptions_new_result',
                                                     ('All exceptions occurred in publishing a '
                                                      'message after a new result'),
                                                     registry=registry)
