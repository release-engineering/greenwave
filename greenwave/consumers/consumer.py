# SPDX-License-Identifier: GPL-2.0+
import logging
import requests

import fedora_messaging.api
import fedora_messaging.exceptions

import greenwave.app_factory
import greenwave.decision

from greenwave.monitor import (
    decision_changed_counter,
    decision_failed_counter,
    decision_unchanged_counter,
    messaging_tx_sent_ok_counter,
    messaging_tx_failed_counter,
)
from greenwave.policies import applicable_decision_context_product_version_pairs
from greenwave.utils import right_before_this_time


from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

log = logging.getLogger(__name__)


def _equals_except_keys(lhs, rhs, except_keys):
    keys = lhs.keys() - except_keys
    return lhs.keys() == rhs.keys() \
        and all(lhs[key] == rhs[key] for key in keys)


def _is_decision_unchanged(old_decision, decision):
    """
    Returns true only if new decision is same as old one
    (ignores result_id values).
    """
    if old_decision is None or decision is None:
        return old_decision == decision

    requirements_keys = ('satisfied_requirements', 'unsatisfied_requirements')
    if not _equals_except_keys(old_decision, decision, requirements_keys):
        return False

    ignore_keys = ('result_id',)
    for key in requirements_keys:
        old_requirements = old_decision[key]
        requirements = decision[key]
        if len(old_requirements) != len(requirements):
            return False

        for old_requirement, requirement in zip(old_requirements, requirements):
            if not _equals_except_keys(old_requirement, requirement, ignore_keys):
                return False

    return True


class Consumer:
    """
    Base class for consumers.
    """
    config_key = 'greenwave_handler'
    hub_config_prefix = 'greenwave_consumer_'
    default_topic = 'item.new'
    monitor_labels = {'handler': 'greenwave_consumer'}
    context = None

    def __init__(self, hub, *args, **kwargs):
        """
        Initialize the consumer, subscribing it to the appropriate topics.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub from which this handler is consuming
                messages. It is used to look up the hub config.
        """

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        suffix = hub.config.get(f'{self.hub_config_prefix}topic_suffix', self.default_topic)
        self.topic = ['.'.join([prefix, env, suffix])]

        config = kwargs.pop('config', None)

        self.flask_app = greenwave.app_factory.create_app(config)
        self.greenwave_api_url = self.flask_app.config['GREENWAVE_API_URL']
        log.info('Greenwave handler listening on: %s', self.topic)

    def consume(self, message):
        """
        Process the given message and take action.

        Args:
            message (fedora_messaging.message.Message): A fedora message about a new item.
        """
        try:
            message = message.get('body', message)
            log.debug('Processing message "%s"', message)
            self.context = TraceContextTextMapPropagator().extract(message)

            with self.flask_app.app_context():
                self._consume_message(message)
        except Exception:  # pylint: disable=broad-except
            # Disallow propagating any other exception, otherwise NACK is sent
            # and the message is scheduled to be received later. But it seems
            # these messages can be only received by other consumer (or after
            # restart) otherwise the messages can block the queue completely.
            log.exception('Unexpected exception')

    def _inc(self, messaging_counter):
        """Helper method to increase monitoring counter."""
        messaging_counter.labels(**self.monitor_labels).inc()

    def _publish_decision_update_fedora_messaging(self, decision):
        try:
            TraceContextTextMapPropagator().inject(decision, self.context)
            msg = fedora_messaging.api.Message(
                topic='greenwave.decision.update',
                body=decision
            )
            fedora_messaging.api.publish(msg)
            self._inc(messaging_tx_sent_ok_counter)
        except fedora_messaging.exceptions.PublishReturned as e:
            log.error(
                'Fedora Messaging broker rejected message %s: %s',
                msg.id, e)
        except fedora_messaging.exceptions.ConnectionException as e:
            log.error('Error sending message %s: %s', msg.id, e)
            self._inc(messaging_tx_failed_counter)
        except Exception:  # pylint: disable=broad-except
            log.exception('Error sending fedora-messaging message')
            self._inc(messaging_tx_failed_counter)

    def _old_and_new_decisions(self, submit_time, **request_data):
        """Returns decision before and after submit time."""
        greenwave_url = self.greenwave_api_url + '/decision'
        log.debug('querying greenwave at: %s', greenwave_url)

        try:
            decision = greenwave.decision.make_decision(request_data, self.flask_app.config)

            request_data['when'] = right_before_this_time(submit_time)
            old_decision = greenwave.decision.make_decision(request_data, self.flask_app.config)
            log.debug('old decision: %s', old_decision)
        except requests.exceptions.HTTPError as e:
            log.exception('Failed to retrieve decision for data=%s, error: %s', request_data, e)
            return None, None

        return old_decision, decision

    def _publish_decision_change(
            self,
            submit_time,
            subject,
            testcase,
            product_version,
            publish_testcase):

        policy_attributes = dict(
            subject=subject,
            testcase=testcase,
        )

        if product_version:
            policy_attributes['product_version'] = product_version

        policies = self.flask_app.config['policies']
        contexts_product_versions = applicable_decision_context_product_version_pairs(
            policies, **policy_attributes)

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
                log.debug('Decision unchanged: %s', decision)
                self._inc(decision_unchanged_counter.labels(decision_context=decision_context))
                continue

            self._inc(decision_changed_counter.labels(decision_context=decision_context))

            decision.update({
                'subject_type': subject.type,
                'subject_identifier': subject.identifier,
                # subject is for backwards compatibility only:
                'subject': [subject.to_dict()],
                'decision_context': decision_context,
                'product_version': product_version,
                'previous': old_decision,
            })
            if publish_testcase:
                decision['testcase'] = testcase

            log.info('Publishing a decision update message: %r', decision)
            self._publish_decision_update_fedora_messaging(decision)
