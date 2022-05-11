# SPDX-License-Identifier: GPL-2.0+
from mock import Mock, patch
from pytest import raises

from greenwave.monitor import Counter, Histogram, stats_client


def test_counter_to_str():
    assert str(Counter('total_decisions')) == 'total_decisions'


def test_counter_to_str_with_labels():
    counter = Counter('total_decisions').labels(handler='test')
    assert str(counter) == 'total_decisions[handler=test]'


def test_counter_no_host_set(monkeypatch):
    with patch('greenwave.monitor.StatsClient') as client:
        monkeypatch.delenv('GREENWAVE_STATSD_HOST', raising=False)
        stats_client.cache_clear()
        Counter('total_decisions').inc()
        client.assert_not_called()


def test_counter_empty_host_set(monkeypatch):
    with patch('greenwave.monitor.StatsClient') as client:
        monkeypatch.setenv('GREENWAVE_STATSD_HOST', '')
        stats_client.cache_clear()
        Counter('total_decisions').inc()
        client.assert_not_called()


def test_counter_inc(monkeypatch):
    with patch('greenwave.monitor.StatsClient') as client:
        monkeypatch.setenv('GREENWAVE_STATSD_HOST', 'localhost:99999')
        stats_client.cache_clear()
        Counter('total_decisions').inc()
        client.assert_called_once()
        stats_client().incr.assert_called_once_with('total_decisions')


def test_counter_count_exceptions(monkeypatch):
    with patch('greenwave.monitor.StatsClient') as client:
        monkeypatch.setenv('GREENWAVE_STATSD_HOST', 'localhost:99999')
        stats_client.cache_clear()
        tested_function = Mock(side_effect=RuntimeError('some exception'))
        decorator = Counter('decision_exceptions').count_exceptions()
        wrapper = decorator(tested_function)

        with raises(RuntimeError, match='some exception'):
            wrapper(1, a=2, b=3)

        tested_function.assert_called_once_with(1, a=2, b=3)

        client.assert_called_once()
        stats_client().incr.assert_called_once_with('decision_exceptions')


def test_histogram_time(monkeypatch):
    with patch('greenwave.monitor.StatsClient') as client:
        monkeypatch.setenv('GREENWAVE_STATSD_HOST', 'localhost:99999')
        stats_client.cache_clear()
        timed_function = Mock()
        decorator = Histogram('decision_duration').time()
        wrapper = decorator(timed_function)

        wrapper(1, a=2, b=3)
        timed_function.assert_called_once_with(1, a=2, b=3)

        client.assert_called_once()
        stats_client().timer.assert_called_once_with('decision_duration')
