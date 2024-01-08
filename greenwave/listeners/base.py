# SPDX-License-Identifier: GPL-2.0+
import json
import logging
import os
import signal
import threading
import uuid

import stomp
from opentelemetry.context import Context
from requests.exceptions import HTTPError

import greenwave.app_factory
from greenwave.logger import init_logging, log_to_stdout
from greenwave.monitor import (
    decision_changed_counter,
    decision_failed_counter,
    decision_unchanged_counter,
    messaging_rx_counter,
    messaging_rx_failed_counter,
    messaging_rx_ignored_counter,
    messaging_rx_processed_ok_counter,
    messaging_tx_failed_counter,
    messaging_tx_sent_ok_counter,
)
from greenwave.policies import applicable_decision_context_product_version_pairs
from greenwave.utils import right_before_this_time

from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


GREENWAVE_LISTENER_PREFIX = "greenwave"


def _equals_except_keys(lhs, rhs, except_keys):
    keys = lhs.keys() - except_keys
    return lhs.keys() == rhs.keys() and all(lhs[key] == rhs[key] for key in keys)


def _is_decision_unchanged(old_decision, decision):
    """
    Returns true only if new decision is same as old one
    (ignores result_id values).
    """
    requirements_keys = ("satisfied_requirements", "unsatisfied_requirements")
    if not _equals_except_keys(old_decision, decision, requirements_keys):
        return False

    ignore_keys = ("result_id",)
    for key in requirements_keys:
        old_requirements = old_decision[key]
        requirements = decision[key]
        if len(old_requirements) != len(requirements):
            return False

        for old_requirement, requirement in zip(old_requirements, requirements):
            if not _equals_except_keys(old_requirement, requirement, ignore_keys):
                return False

    return True


def _send_ack(listener, headers):
    listener.connection.ack(headers["message-id"], listener.uid)


def _send_nack(listener, headers):
    listener.connection.nack(headers["message-id"], listener.uid)


class BaseListener(stomp.ConnectionListener):
    monitor_labels = {"handler": "greenwave_listener"}

    def __init__(self, uid_suffix, config_obj=None):
        super().__init__()
        self.connection = None
        self.topic = None

        self.connection_condition = threading.Condition()
        self.connecting = False
        self.stop = False

        self.uid = f"{GREENWAVE_LISTENER_PREFIX}-{uid_suffix}-{uuid.uuid1().hex}"

        init_logging()
        log_to_stdout(logging.DEBUG)
        self.app = greenwave.app_factory.create_app(config_obj)

        self.destination = self.app.config["LISTENER_DECISION_UPDATE_DESTINATION"]

        self.context = None

    def on_error(self, frame):
        self.app.logger.warning("Received an error: %s", frame.body)

    def on_message(self, frame):
        with self.connection_condition:
            if self.stop:
                _send_nack(self, frame.headers)
                return

        self.app.logger.debug("Received a message: %s", frame.body)
        _send_ack(self, frame.headers)
        self._inc(messaging_rx_counter)

        try:
            data = json.loads(frame.body)
        except json.JSONDecodeError as e:
            self.app.logger.debug("Failed to decode JSON message: %s", e)
            self._inc(messaging_rx_ignored_counter)
            return

        try:
            with self.app.app_context():
                processed = self._consume_message(data)
        except BaseException:
            self._inc(messaging_rx_failed_counter)
            raise

        if processed:
            self._inc(messaging_rx_processed_ok_counter)
        else:
            self._inc(messaging_rx_ignored_counter)

    def connect(self):
        with self.connection_condition:
            if self.connecting or self.connection.is_connected():
                return

            self.app.logger.debug("Connecting listener")
            self.connecting = True
            try:
                self.connection.connect(wait=True)
            except BaseException:
                self.app.logger.exception("Failed to connect")
                self._terminate()
            finally:
                self.connecting = False

    def subscribe(self):
        self.connection.subscribe(
            destination=self.topic, id=self.uid, ack="client-individual"
        )
        self.app.logger.debug("Subscribed %s to %s", self.uid, self.topic)

    def on_connected(self, frame):
        self.app.logger.debug("Listener: on_connected")
        self.subscribe()

    def on_disconnected(self):
        self.app.logger.debug("Listener: on_disconnected")
        self._terminate()

    def on_receiver_loop_completed(self, frame):
        """This is also called on heartbeat timeout."""
        self.app.logger.debug("Listener: on_receiver_loop_completed")
        self._terminate()

    def listen(self):
        if self.connection is not None:
            self.app.logger.warning("Already connected")
            return

        def handler(signum, frame):
            self.app.logger.warning("Stopping listener on signal %s", signum)
            self.disconnect()

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, handler)

        hosts = self.app.config["LISTENER_HOSTS"]
        hosts_and_ports = [tuple(url.split(":")) for url in hosts.split(",")]
        connection_args = self.app.config["LISTENER_CONNECTION"]
        if not connection_args.get("host_and_ports"):
            connection_args["host_and_ports"] = hosts_and_ports

        connection = stomp.connect.StompConnection11(**connection_args)

        ssl_args = self.app.config["LISTENER_CONNECTION_SSL"]
        if ssl_args:
            if not ssl_args.get("for_hosts"):
                ssl_args["for_hosts"] = hosts_and_ports
            connection.set_ssl(**ssl_args)

        self.connection = connection
        connection.set_listener("", self)
        self.connect()

        self.app.logger.info("Listening on %s", self.topic)

    def disconnect(self):
        self.app.logger.debug("Disconnecting listener")
        with self.connection_condition:
            self.stop = True
            self.connection.disconnect()

    def _terminate(self):
        self.disconnect()
        os.kill(os.getpid(), signal.SIGQUIT)

    def _consume_message(self, message):
        """
        Processes messages and either calls
        self._publish_decision_change() and returns True or just
        returns False.
        """
        self.context: Context = TraceContextTextMapPropagator().extract(message)

    def _inc(self, messaging_counter):
        """Helper method to increase monitoring counter."""
        messaging_counter.labels(**self.monitor_labels).inc()

    def _publish_decision_update(self, decision):
        TraceContextTextMapPropagator().inject(decision, self.context)
        message = {"msg": decision, "topic": self.destination}
        body = json.dumps(message)
        while True:
            try:
                headers = {
                    "subject_type": decision["subject_type"],
                    "subject_identifier": decision["subject_identifier"],
                    "product_version": decision["product_version"],
                    "decision_context": decision["decision_context"],
                    "policies_satisfied": str(decision["policies_satisfied"]).lower(),
                    "summary": decision["summary"],
                }
                self.connection.send(
                    body=body, headers=headers, destination=self.destination
                )
                break
            except stomp.exception.NotConnectedException:
                self.app.logger.warning("Reconnecting to send message")
                self.connect()
            except Exception:
                self.app.logger.exception("Error sending decision update message")
                self._inc(messaging_tx_failed_counter)
                raise

        self._inc(messaging_tx_sent_ok_counter)

    def _old_and_new_decisions(self, submit_time, **request_data):
        """Returns decision before and after submit time."""
        try:
            decision = greenwave.decision.make_decision(request_data, self.app.config)

            request_data["when"] = right_before_this_time(submit_time)
            old_decision = greenwave.decision.make_decision(
                request_data, self.app.config
            )
            self.app.logger.debug("old decision: %s", old_decision)
        except HTTPError as e:
            self.app.logger.exception(
                "Failed to retrieve decision for data=%s, error: %s", request_data, e
            )
            return None, None

        return old_decision, decision

    def _publish_decision_change(
        self, submit_time, subject, testcase, product_version, publish_testcase
    ):

        policy_attributes = dict(
            subject=subject,
            testcase=testcase,
        )

        if product_version:
            policy_attributes["product_version"] = product_version

        policies = self.app.config["policies"]
        contexts_product_versions = applicable_decision_context_product_version_pairs(
            policies, **policy_attributes
        )

        for decision_context, product_version in sorted(contexts_product_versions):
            old_decision, decision = self._old_and_new_decisions(
                submit_time,
                decision_context=decision_context,
                product_version=product_version,
                subject_type=subject.type,
                subject_identifier=subject.identifier,
            )
            if decision is None:
                self._inc(decision_failed_counter.labels(decision_context=decision_context))
                continue

            if _is_decision_unchanged(old_decision, decision):
                self.app.logger.debug(
                    "Skipped emitting fedora message, decision did not change: %s", decision
                )
                self._inc(decision_unchanged_counter.labels(decision_context=decision_context))
                continue

            self._inc(decision_changed_counter.labels(decision_context=decision_context))

            decision.update(
                {
                    "subject_type": subject.type,
                    "subject_identifier": subject.identifier,
                    # subject is for backwards compatibility only:
                    "subject": [subject.to_dict()],
                    "decision_context": decision_context,
                    "product_version": product_version,
                    "previous": old_decision,
                }
            )
            if publish_testcase:
                decision["testcase"] = testcase

            self.app.logger.info("Publishing decision change message: %r", decision)
            self._publish_decision_update(decision)
