# SPDX-License-Identifier: GPL-2.0+

import importlib
import os
import pytest
import requests
import greenwave.monitor


min_num_of_metrics = 23


def test_metrics(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'api/v1.0/metrics')

    assert r.status_code == 200
    assert len([l for l in r.text.splitlines()
                if l.startswith('# TYPE')]) >= min_num_of_metrics


def test_standalone_metrics_server_disabled_by_default(requests_session):
    with pytest.raises(requests.exceptions.ConnectionError):
        requests_session.get('http://127.0.0.1:10040/metrics')


def test_standalone_metrics_server(requests_session):
    os.environ['MONITOR_STANDALONE_METRICS_SERVER_ENABLE'] = 'true'
    importlib.reload(greenwave.monitor)

    r = requests_session.get('http://127.0.0.1:10040/metrics')

    assert len([l for l in r.text.splitlines()
                if l.startswith('# TYPE')]) >= min_num_of_metrics
