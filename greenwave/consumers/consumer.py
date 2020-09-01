# SPDX-License-Identifier: GPL-2.0+
import fedmsg
import logging
import requests

import fedmsg.consumers

import greenwave.app_factory
from greenwave.monitor import (
    publish_decision_exceptions_result_counter,
    messaging_tx_to_send_counter, messaging_tx_stopped_counter,
    messaging_tx_sent_ok_counter, messaging_tx_failed_counter)
from greenwave.policies import applicable_decision_context_product_version_pairs
from greenwave.utils import right_before_this_time

import greenwave.resources

try:
    import fedora_messaging.api
    import fedora_messaging.exceptions
except ImportError:
    pass

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


class Consumer(fedmsg.consumers.FedmsgConsumer):
    """
    Base class for consumers.
    """
    config_key = 'greenwave_handler'
    hub_config_prefix = 'greenwave_consumer_'
    default_topic = 'item.new'
    monitor_labels = {'handler': 'greenwave_consumer'}

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
        self.fedmsg_config = fedmsg.config.load_config()

        config = kwargs.pop('config', None)

        super().__init__(hub, *args, **kwargs)

        self.flask_app = greenwave.app_factory.create_app(config)
        self.greenwave_api_url = self.flask_app.config['GREENWAVE_API_URL']
        log.info('Greenwave handler listening on: %s', self.topic)

    def consume(self, message):
        """
        Process the given message and take action.

        Args:
            message (munch.Munch): A fedmsg about a new item.
        """
        try:
            message = message.get('body', message)
            log.debug('Processing message "%s"', message)

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

    def _publish_decision_update_fedmsg(self, decision):
        try:
            fedmsg.publish(topic='decision.update', msg=decision)
            self._inc(messaging_tx_sent_ok_counter)
        except Exception:
            log.exception('Error sending fedmsg message')
            self._inc(messaging_tx_failed_counter)
            raise

    def _publish_decision_update_fedora_messaging(self, decision):
        try:
            msg = fedora_messaging.api.Message(
                topic='greenwave.decision.update',
                body=decision
            )
            fedora_messaging.api.publish(msg)
            self._inc(messaging_tx_sent_ok_counter)
        except fedora_messaging.exceptions.PublishReturned as e:
            log.warning(
                'Fedora Messaging broker rejected message %s: %s',
                msg.id, e)
            self._inc(messaging_tx_stopped_counter)
        except fedora_messaging.exceptions.ConnectionException as e:
            log.warning('Error sending message %s: %s', msg.id, e)
            self._inc(messaging_tx_failed_counter)
        except Exception:  # pylint: disable=broad-except
            log.exception('Error sending fedora-messaging message')
            self._inc(messaging_tx_failed_counter)

    def _old_and_new_decisions(self, submit_time, **request_data):
        """Returns decision before and after submit time."""
        greenwave_url = self.greenwave_api_url + '/decision'
        log.debug('querying greenwave at: %s', greenwave_url)

        try:
            decision = greenwave.resources.retrieve_decision(greenwave_url, request_data)

            request_data['when'] = right_before_this_time(submit_time)
            old_decision = greenwave.resources.retrieve_decision(greenwave_url, request_data)
            log.debug('old decision: %s', old_decision)
        except requests.exceptions.HTTPError as e:
            log.exception('Failed to retrieve decision for data=%s, error: %s', request_data, e)
            self._inc(messaging_tx_stopped_counter)
            return None, None

        return old_decision, decision

    @publish_decision_exceptions_result_counter.count_exceptions()
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

        log.info('Getting greenwave info')

        for decision_context, product_version in sorted(contexts_product_versions):
            self._inc(messaging_tx_to_send_counter)

            old_decision, decision = self._old_and_new_decisions(
                submit_time,
                decision_context=decision_context,
                product_version=product_version,
                subject_type=subject.type,
                subject_identifier=subject.identifier,
            )
            if decision is None:
                continue

            if _is_decision_unchanged(old_decision, decision):
                log.debug('Skipped emitting fedmsg, decision did not change: %s', decision)
                self._inc(messaging_tx_stopped_counter)
                continue

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

            log.info(
                'Emitting a message on the bus, %r, with the topic '
                '"greenwave.decision.update"', decision)
            if self.flask_app.config['MESSAGING'] == 'fedmsg':
                log.debug('  - to fedmsg')
                self._publish_decision_update_fedmsg(decision)
            elif self.flask_app.config['MESSAGING'] == 'fedora-messaging':
                log.debug('  - to fedora-messaging')
                self._publish_decision_update_fedora_messaging(decision)

            self._inc(messaging_tx_stopped_counter)
