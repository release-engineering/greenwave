# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
The "resultsdb handler".

This module is responsible for listening new results from ResultsDB. When a new
result is received, Greenwave will check all applicable policies for that item,
and if the new result causes the decision to change it will publish a message
to the message bus about the newly satisfied/unsatisfied policy.
"""

import collections
import logging

import dogpile.cache
import fedmsg.consumers
import requests

import greenwave.cache
import greenwave.resources
from greenwave.utils import load_config

requests_session = requests.Session()


log = logging.getLogger(__name__)


class ResultsDBHandler(fedmsg.consumers.FedmsgConsumer):
    """
    Handle a new result.

    Attributes:
        topic (list): A list of strings that indicate which fedmsg topics this consumer listens to.
    """

    config_key = 'resultsdb_handler'

    def __init__(self, hub, *args, **kwargs):
        """
        Initialize the ResultsDBHandler, subscribing it to the appropriate topics.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub from which this handler is consuming
                messages. It is used to look up the hub config.
        """

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        suffix = hub.config.get('resultsdb_topic_suffix', 'taskotron.result.new')
        self.topic = ['.'.join([prefix, env, suffix])]
        self.fedmsg_config = fedmsg.config.load_config()

        super(ResultsDBHandler, self).__init__(hub, *args, **kwargs)

        # Initialize the cache.
        self.cache = dogpile.cache.make_region(
            key_mangler=dogpile.cache.util.sha1_mangle_key)
        self.cache.configure(**hub.config['greenwave_cache'])

        log.info('Greenwave resultsdb handler listening on: %s', self.topic)

    @staticmethod
    def announcement_subjects(config, message):
        """ Yields subjects for announcement consideration from the message.

        Args:
            config (dict): The greenwave configuration.
            message (munch.Munch): A fedmsg about a new result.
        """

        try:
            data = message['msg']['data']  # New format
        except KeyError:
            data = message['msg']['task']  # Old format

        announcement_keys = [
            set(keys) for keys in config['ANNOUNCEMENT_SUBJECT_KEYS']
        ]

        def _decode(value):
            """ Decode either a string or a list of strings. """
            if len(value) == 1:
                value = value[0]
            return value.decode('utf-8')

        for keys in announcement_keys:
            if keys.issubset(data.keys()):
                yield {key.decode('utf-8'): _decode(data[key]) for key in keys}

    def consume(self, message):
        """
        Process the given message and take action.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """
        message = message.get('body', message)
        log.debug('Processing message "%s"', message)
        config = load_config()

        try:
            testcase = message['msg']['testcase']['name']  # New format
        except KeyError:
            testcase = message['msg']['task']['name']  # Old format

        try:
            result_id = message['msg']['id']  # New format
        except KeyError:
            result_id = message['msg']['result']['id']  # Old format

        for subject in self.announcement_subjects(config, message):
            log.debug('Considering subject "%s"', subject)
            self._invalidate_cache(subject)
            self._publish_decision_changes(config, subject, result_id, testcase)

    def _publish_decision_changes(self, config, subject, result_id, testcase):
        """
        Process the given subject and publish a message if the decision is changed.

        Args:
            config (dict): The greenwave configuration.
            subject (munch.Munch): A subject argument, used to query greenwave.
            result_id (int): A result ID to ignore for comparison.
            testcase (munch.Munch): The name of a testcase to consider.
        """

        # Build a set of all policies which might apply to this new results
        applicable_policies = set()
        for policy in config['policies']:
            for rule in policy.rules:
                if rule.test_case_name == testcase:
                    applicable_policies.add(policy)
        log.debug("messaging: found %i applicable policies of %i for testcase %r",
                  len(applicable_policies), len(config['policies']), testcase)

        # Given all of our applicable policies, build a map of all decision
        # context we know about, and which product versions they relate to.
        decision_contexts = collections.defaultdict(set)
        for policy in applicable_policies:
            versions = set(policy.product_versions)
            decision_contexts[policy.decision_context].update(versions)
        log.debug("messaging: found %i decision contexts", len(decision_contexts))

        # For every context X version combination, ask greenwave if this new
        # result pushes any decisions over a threshold.
        for decision_context, product_versions in decision_contexts.items():
            for product_version in product_versions:
                greenwave_url = self.fedmsg_config['greenwave_api_url'] + '/decision'

                data = {
                    'decision_context': decision_context,
                    'product_version': product_version,
                    'subject': [subject],
                }
                decision = greenwave.resources.retrieve_decision(greenwave_url, data)

                # get old decision
                data.update({
                    'ignore_result': [result_id],
                })
                old_decision = greenwave.resources.retrieve_decision(greenwave_url, data)

                if decision != old_decision:
                    decision.update({
                        'subject': [subject],
                        'decision_context': decision_context,
                        'product_version': product_version,
                        'previous': old_decision,
                    })
                    log.debug('Emitted a fedmsg, %r, on the "%s" topic', decision,
                              'greenwave.decision.update')
                    fedmsg.publish(topic='decision.update', msg=decision)

    def _invalidate_cache(self, subject):
        """
        Process the given subject and delete cache keys as necessary.

        Args:
            subject (munch.Munch): A subject argument, used to query greenwave.
        """
        namespace = None
        fn = greenwave.resources.retrieve_results
        key = greenwave.cache.key_generator(namespace, fn)(subject)
        if not self.cache.get(key):
            log.debug("No cache value found for %r", key)
        else:
            log.debug("Invalidating cache for %r", key)
            self.cache.delete(key)
