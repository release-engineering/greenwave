# SPDX-License-Identifier: GPL-2.0+
import logging
import os
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka import Message as KafkaMessage

_log = logging.getLogger(__name__)

REQUIRED_KAFKA_KEYS = (
    "resultsdb_topic",
    "waiverdb_topic",
    "decision_topic",
    "consumer",
    "producer",
)


def parse_kafka_config(
    app_config,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = app_config.get("KAFKA")
    if not isinstance(config, dict):
        raise RuntimeError(
            f"KAFKA configuration is invalid, expected a dict, got: {config!r}"
        )

    missing = [key for key in REQUIRED_KAFKA_KEYS if key not in config]
    if missing:
        raise RuntimeError(f"Invalid KAFKA configuration: missing {', '.join(missing)}")
    if not isinstance(config["consumer"], dict) or not isinstance(
        config["producer"], dict
    ):
        raise RuntimeError(
            "Invalid KAFKA configuration: consumer and producer must be dicts"
        )

    username = os.environ.get("GREENWAVE_KAFKA_SASL_USERNAME")
    password = os.environ.get("GREENWAVE_KAFKA_SASL_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "GREENWAVE_KAFKA_SASL_USERNAME and GREENWAVE_KAFKA_SASL_PASSWORD "
            "environment variables are required"
        )

    sasl = {"sasl.username": username, "sasl.password": password}
    consumer_config = {**config["consumer"], **sasl}
    producer_config = {**config["producer"], **sasl}
    return config, consumer_config, producer_config


class KafkaBus:
    """Kafka consumer and producer used by Greenwave listeners."""

    def __init__(self, app_config, group_id: str) -> None:
        kafka_config, consumer_config, producer_config = parse_kafka_config(app_config)
        consumer_config = {**consumer_config, "group.id": group_id}
        consumer_config.setdefault("enable.auto.commit", False)
        self.config = kafka_config
        self.flush_timeout_seconds = float(
            kafka_config.get("flush_timeout_seconds", 20.0)
        )
        self.consumer = Consumer(consumer_config)
        self.producer = Producer(producer_config)

    def subscribe(self, topic: str) -> None:
        self.consumer.subscribe([topic])

    def poll(self, timeout: float = 1.0) -> KafkaMessage | None:
        return self.consumer.poll(timeout)

    def commit(self, msg: KafkaMessage) -> None:
        self.consumer.commit(message=msg)

    def publish(self, topic: str, body: str, headers: dict[str, str]) -> None:
        delivery_error = None

        def _delivery_callback(err: KafkaError | None, _msg: KafkaMessage) -> None:
            nonlocal delivery_error
            if err is not None:
                delivery_error = delivery_error or KafkaException(err)

        kafka_headers: list[tuple[str, str | bytes | None]] = [
            (key, value.encode("utf-8")) for key, value in headers.items()
        ]
        self.producer.produce(
            topic,
            value=body.encode("utf-8"),
            headers=kafka_headers,
            on_delivery=_delivery_callback,
        )
        remaining = self.producer.flush(timeout=self.flush_timeout_seconds)
        if remaining > 0:
            raise KafkaException(
                KafkaError(
                    KafkaError._MSG_TIMED_OUT,
                    f"{remaining} message(s) were not delivered within timeout",
                )
            )
        if delivery_error is not None:
            raise delivery_error

    def close(self) -> None:
        try:
            self.consumer.close()
        except Exception:
            _log.debug("Error closing Kafka consumer", exc_info=True)
        try:
            self.producer.flush()
        except Exception:
            _log.debug("Error flushing Kafka producer", exc_info=True)
