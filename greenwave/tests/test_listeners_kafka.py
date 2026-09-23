# SPDX-License-Identifier: GPL-2.0+
import json
from unittest.mock import Mock, patch

from confluent_kafka import KafkaError, KafkaException
from pytest import fixture, raises

from greenwave.config import TestingConfig
from greenwave.listeners.kafka import KafkaBus, parse_kafka_config
from greenwave.listeners.resultsdb import ResultsDBListener
from greenwave.listeners.waiverdb import WaiverDBListener


class KafkaTestingConfig(TestingConfig):
    LISTENER_BACKEND = "kafka"
    KAFKA = {
        "resultsdb_topic": "qa.eng.resultsdb.result.new",
        "waiverdb_topic": "qa.eng.waiverdb.waiver.new",
        "decision_topic": "qa.eng.greenwave.decision.update",
        "consumer": {
            "bootstrap.servers": "localhost:9092",
            "client.id": "greenwave-test",
            "enable.auto.commit": False,
            "auto.offset.reset": "latest",
        },
        "producer": {
            "bootstrap.servers": "localhost:9092",
            "client.id": "greenwave-test",
            "retries": 3,
        },
        "flush_timeout_seconds": 15.0,
    }


@fixture
def kafka_env(monkeypatch):
    monkeypatch.setenv("GREENWAVE_KAFKA_SASL_USERNAME", "alice")
    monkeypatch.setenv("GREENWAVE_KAFKA_SASL_PASSWORD", "secret")


def _kafka_config():
    return {
        "KAFKA": {
            "resultsdb_topic": "qa.eng.resultsdb.result.new",
            "waiverdb_topic": "qa.eng.waiverdb.waiver.new",
            "decision_topic": "qa.eng.greenwave.decision.update",
            "consumer": {
                "bootstrap.servers": "localhost:9092",
                "client.id": "greenwave-test",
            },
            "producer": {
                "bootstrap.servers": "localhost:9092",
                "client.id": "greenwave-test",
            },
            "flush_timeout_seconds": 15.0,
        }
    }


def test_parse_kafka_config_injects_sasl(kafka_env):
    kafka_config, consumer_config, producer_config = parse_kafka_config(_kafka_config())
    assert kafka_config["decision_topic"] == "qa.eng.greenwave.decision.update"
    assert consumer_config["sasl.username"] == "alice"
    assert producer_config["sasl.password"] == "secret"


def test_parse_kafka_config_missing_sasl(monkeypatch):
    monkeypatch.delenv("GREENWAVE_KAFKA_SASL_USERNAME", raising=False)
    monkeypatch.delenv("GREENWAVE_KAFKA_SASL_PASSWORD", raising=False)
    with raises(RuntimeError, match="GREENWAVE_KAFKA_SASL_USERNAME"):
        parse_kafka_config(_kafka_config())


def test_parse_kafka_config_invalid():
    with raises(RuntimeError, match="Invalid KAFKA configuration"):
        parse_kafka_config({"KAFKA": {"producer": {}}})


def test_parse_kafka_config_not_dict():
    with raises(RuntimeError, match="expected a dict"):
        parse_kafka_config({"KAFKA": None})


def test_resultsdb_listener_uses_kafka_topics():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    assert listener._backend == "kafka"
    assert listener.topic == "qa.eng.resultsdb.result.new"
    assert listener.destination == "qa.eng.greenwave.decision.update"


def test_waiverdb_listener_uses_kafka_topics():
    listener = WaiverDBListener(config_obj=KafkaTestingConfig)
    assert listener._backend == "kafka"
    assert listener.topic == "qa.eng.waiverdb.waiver.new"
    assert listener.destination == "qa.eng.greenwave.decision.update"


def test_default_backend_is_stomp():
    listener = ResultsDBListener(config_obj=TestingConfig)
    assert listener._backend == "stomp"
    assert listener.topic.endswith("VirtualTopic.eng.resultsdb.result.new")


def test_listen_kafka_starts_consumer(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer") as mock_consumer_cls,
        patch("greenwave.listeners.kafka.Producer") as mock_producer_cls,
    ):
        mock_consumer = Mock()
        mock_consumer.poll.return_value = None
        mock_consumer_cls.return_value = mock_consumer
        mock_producer_cls.return_value = Mock()

        listener = ResultsDBListener(config_obj=KafkaTestingConfig)
        try:
            listener.listen()
            mock_consumer.subscribe.assert_called_once_with(
                ["qa.eng.resultsdb.result.new"]
            )
            consumer_config = mock_consumer_cls.call_args[0][0]
            assert consumer_config["group.id"] == "greenwave-resultsdb"
            assert consumer_config["sasl.username"] == "alice"
            assert consumer_config["enable.auto.commit"] is False
            producer_config = mock_producer_cls.call_args[0][0]
            assert producer_config["sasl.password"] == "secret"
            assert listener._kafka_thread is not None
            assert listener._kafka_thread.daemon
            listener.listen()
            assert mock_consumer.subscribe.call_count == 1
        finally:
            listener.disconnect()


def test_handle_kafka_message_commits_after_success():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    msg = Mock()
    msg.offset.return_value = 12
    msg.value.return_value = json.dumps(
        {
            "outcome": "QUEUED",
            "testcase": {"name": "dist.rpmdeplint"},
            "submit_time": "2019-03-25T16:34:41.882620",
            "data": {"item": ["nvr-1.0-1"], "type": ["koji_build"]},
        }
    ).encode()

    listener._handle_kafka_message(msg)

    listener._kafka_bus.commit.assert_called_once_with(msg)


def test_handle_kafka_message_commits_invalid_json():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    msg = Mock()
    msg.offset.return_value = 12
    msg.value.return_value = b"not-json"

    listener._handle_kafka_message(msg)

    listener._kafka_bus.commit.assert_called_once_with(msg)


def test_handle_kafka_message_does_not_commit_on_failure():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    msg = Mock()
    msg.offset.return_value = 12
    msg.value.return_value = json.dumps({"outcome": "PASSED"}).encode()

    with patch.object(listener, "_consume_message", side_effect=RuntimeError("boom")):
        with raises(RuntimeError, match="boom"):
            listener._handle_kafka_message(msg)

    listener._kafka_bus.commit.assert_not_called()


def test_publish_decision_update_kafka():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    decision = {
        "subject_type": "koji_build",
        "subject_identifier": "nvr-1.0-1",
        "product_version": "fedora-rawhide",
        "decision_context": "test_context",
        "policies_satisfied": True,
        "summary": "All required tests passed",
    }

    listener._publish_decision_update(decision)

    listener._kafka_bus.publish.assert_called_once()
    topic, body, headers = listener._kafka_bus.publish.call_args[0]
    assert topic == "qa.eng.greenwave.decision.update"
    payload = json.loads(body)
    assert payload["topic"] == topic
    assert payload["msg"]["subject_identifier"] == "nvr-1.0-1"
    assert headers["policies_satisfied"] == "true"


def test_publish_decision_update_kafka_error():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    listener._kafka_bus.publish.side_effect = KafkaException("send failed")
    decision = {
        "subject_type": "koji_build",
        "subject_identifier": "nvr-1.0-1",
        "product_version": "fedora-rawhide",
        "decision_context": "test_context",
        "policies_satisfied": False,
        "summary": "1 of 1 required tests failed",
    }

    with raises(KafkaException):
        listener._publish_decision_update(decision)


def _simulate_successful_produce(mock_producer):
    callbacks = []

    def capture_produce(topic, value=None, headers=None, on_delivery=None):
        callbacks.append(on_delivery)

    def trigger_flush(timeout=None):
        for cb in callbacks:
            if cb:
                cb(None, Mock())
        callbacks.clear()
        return 0

    mock_producer.produce.side_effect = capture_produce
    mock_producer.flush.side_effect = trigger_flush


def test_kafka_bus_publish_success(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer"),
        patch("greenwave.listeners.kafka.Producer") as mock_producer_cls,
    ):
        mock_producer = Mock()
        mock_producer_cls.return_value = mock_producer
        _simulate_successful_produce(mock_producer)

        bus = KafkaBus(_kafka_config(), group_id="greenwave-resultsdb")
        bus.publish(
            "qa.eng.greenwave.decision.update",
            '{"msg": {}}',
            {"summary": "ok"},
        )

        mock_producer.produce.assert_called_once()
        args, kwargs = mock_producer.produce.call_args
        assert args[0] == "qa.eng.greenwave.decision.update"
        assert kwargs["headers"] == [("summary", b"ok")]
        mock_producer.flush.assert_called_with(timeout=15.0)


def test_kafka_bus_publish_delivery_error(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer"),
        patch("greenwave.listeners.kafka.Producer") as mock_producer_cls,
    ):
        mock_producer = Mock()
        mock_producer_cls.return_value = mock_producer
        callbacks = []

        def capture_produce(topic, value=None, headers=None, on_delivery=None):
            callbacks.append(on_delivery)

        def trigger_flush(timeout=None):
            for cb in callbacks:
                if cb:
                    cb(Mock(), None)
            callbacks.clear()
            return 0

        mock_producer.produce.side_effect = capture_produce
        mock_producer.flush.side_effect = trigger_flush

        bus = KafkaBus(_kafka_config(), group_id="greenwave-resultsdb")
        with raises(KafkaException):
            bus.publish("qa.eng.greenwave.decision.update", "{}", {})


def test_parse_kafka_config_consumer_not_dict(kafka_env):
    config = _kafka_config()
    config["KAFKA"]["consumer"] = "nope"
    with raises(RuntimeError, match="consumer and producer must be dicts"):
        parse_kafka_config(config)


def test_kafka_bus_publish_flush_timeout(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer"),
        patch("greenwave.listeners.kafka.Producer") as mock_producer_cls,
    ):
        mock_producer = Mock()
        mock_producer.flush.return_value = 1
        mock_producer_cls.return_value = mock_producer

        bus = KafkaBus(_kafka_config(), group_id="greenwave-resultsdb")
        with raises(KafkaException) as exc_info:
            bus.publish("qa.eng.greenwave.decision.update", "{}", {})

        err = exc_info.value.args[0]
        assert isinstance(err, KafkaError)
        assert err.code() == KafkaError._MSG_TIMED_OUT


def _queued_result_payload():
    return json.dumps(
        {
            "outcome": "QUEUED",
            "testcase": {"name": "dist.rpmdeplint"},
            "submit_time": "2019-03-25T16:34:41.882620",
            "data": {"item": ["nvr-1.0-1"], "type": ["koji_build"]},
        }
    ).encode()


def _kafka_message(error=None, value=None):
    msg = Mock()
    msg.error.return_value = error
    msg.offset.return_value = 12
    msg.value.return_value = value if value is not None else _queued_result_payload()
    return msg


def test_kafka_bus_commit_and_close(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer") as mock_consumer_cls,
        patch("greenwave.listeners.kafka.Producer") as mock_producer_cls,
    ):
        mock_consumer = Mock()
        mock_producer = Mock()
        mock_consumer_cls.return_value = mock_consumer
        mock_producer_cls.return_value = mock_producer
        mock_consumer.close.side_effect = RuntimeError("close failed")
        mock_producer.flush.side_effect = RuntimeError("flush failed")

        bus = KafkaBus(_kafka_config(), group_id="greenwave-resultsdb")
        msg = Mock()
        bus.commit(msg)
        mock_consumer.commit.assert_called_once_with(message=msg)
        bus.close()


def test_handle_kafka_message_processed_ok():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    msg = _kafka_message()

    with patch.object(listener, "_consume_message", return_value=True):
        listener._handle_kafka_message(msg)

    listener._kafka_bus.commit.assert_called_once_with(msg)


def test_handle_kafka_message_stopped():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    listener.stop = True

    listener._handle_kafka_message(_kafka_message())

    listener._kafka_bus.commit.assert_not_called()


def test_kafka_loop_processes_message():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    msg = _kafka_message()
    calls = {"n": 0}

    def poll(_timeout=1.0):
        calls["n"] += 1
        if calls["n"] == 1:
            return msg
        listener.stop = True
        return None

    listener._kafka_bus.poll.side_effect = poll
    listener._kafka_loop()
    listener._kafka_bus.commit.assert_called_once_with(msg)


def test_kafka_loop_ignores_partition_eof():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    error = Mock()
    error.code.return_value = KafkaError._PARTITION_EOF

    def poll(_timeout=1.0):
        listener.stop = True
        return _kafka_message(error=error)

    listener._kafka_bus.poll.side_effect = poll
    listener._kafka_loop()
    listener._kafka_bus.commit.assert_not_called()


def test_kafka_loop_nonfatal_error():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    error = Mock()
    error.code.return_value = KafkaError._TRANSPORT
    error.fatal.return_value = False

    def poll(_timeout=1.0):
        listener.stop = True
        return _kafka_message(error=error)

    listener._kafka_bus.poll.side_effect = poll
    with patch.object(listener, "_terminate") as terminate:
        listener._kafka_loop()
        terminate.assert_not_called()
    listener._kafka_bus.commit.assert_not_called()


def test_kafka_loop_fatal_error():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    error = Mock()
    error.code.return_value = KafkaError._FATAL
    error.fatal.return_value = True

    listener._kafka_bus.poll.return_value = _kafka_message(error=error)
    with patch.object(listener, "_terminate") as terminate:
        listener._kafka_loop()
        terminate.assert_called_once()


def test_kafka_loop_exception_terminates():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    listener._kafka_bus.poll.side_effect = RuntimeError("broker down")
    with patch.object(listener, "_terminate") as terminate:
        listener._kafka_loop()
        terminate.assert_called_once()


def test_disconnect_kafka_closes_bus():
    listener = ResultsDBListener(config_obj=KafkaTestingConfig)
    listener._kafka_bus = Mock()
    listener._kafka_thread = Mock()
    listener._kafka_thread.is_alive.return_value = True
    listener.disconnect()
    listener._kafka_bus.close.assert_called_once()
    listener._kafka_thread.join.assert_called_once_with(timeout=5)


def test_listen_kafka_sigterm_disconnects(kafka_env):
    with (
        patch("greenwave.listeners.kafka.Consumer") as mock_consumer_cls,
        patch("greenwave.listeners.kafka.Producer"),
        patch("greenwave.listeners.base.signal.signal") as mock_signal,
    ):
        mock_consumer = Mock()
        mock_consumer.poll.return_value = None
        mock_consumer_cls.return_value = mock_consumer
        listener = ResultsDBListener(config_obj=KafkaTestingConfig)
        try:
            listener.listen()
            handler = mock_signal.call_args[0][1]
            with patch.object(listener, "disconnect") as disconnect:
                handler(15, None)
                disconnect.assert_called_once()
        finally:
            listener.stop = True
            listener.disconnect()
