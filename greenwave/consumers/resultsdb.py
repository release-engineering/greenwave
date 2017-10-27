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
import copy
import json
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
        self.topic = [
            prefix + '.' + env + '.taskotron.result.new',
        ]
        self.fedmsg_config = fedmsg.config.load_config()

        super(ResultsDBHandler, self).__init__(hub, *args, **kwargs)

        # Initialize the cache.
        self.cache = dogpile.cache.make_region(
            key_mangler=dogpile.cache.util.sha1_mangle_key)
        self.cache.configure(**hub.config['greenwave_cache'])

        log.info('Greenwave resultsdb handler listening on: %s', self.topic)

    def consume(self, message):
        """
        Process the given message and take action.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """
        message = message.get('body', message)
        log.debug('Processing message "%s"', message)
        self._invalidate_cache(message)
        self._publish_decision_changes(message)

    def _publish_decision_changes(self, message):
        """
        Process the given message and publish a message if the decision is changed.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """
        msg = copy.deepcopy(message['msg'])
        task = msg['task']
        testcase = task['name']
        del task['name']
        config = load_config()

        # Build a set of all policies which might apply to this new results
        applicable_policies = set()
        for policy in config['policies']:
            for rule in policy.rules:
                if rule.test_case_name == testcase:
                    applicable_policies.add(policy)

        # Given all of our applicable policies, build a map of all decision
        # context we know about, and which product versions they relate to.
        decision_contexts = collections.defaultdict(set)
        for policy in applicable_policies:
            versions = set(policy.product_versions)
            decision_contexts[policy.decision_context].update(versions)

        # For every context X version combination, ask greenwave if this new
        # result pushes any decisions over a threshold.
        for decision_context, product_versions in decision_contexts.items():
            for product_version in product_versions:
                data = {
                    'decision_context': decision_context,
                    'product_version': product_version,
                    'subject': [task],
                }
                response = requests_session.post(
                    self.fedmsg_config['greenwave_api_url'] + '/decision',
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps(data))
                response.raise_for_status()
                decision = response.json()
                # get old decision
                data.update({
                    'ignore_result': [msg['result']['id']],
                })
                response = requests_session.post(
                    self.fedmsg_config['greenwave_api_url'] + '/decision',
                    headers={'Content-Type': 'application/json'},
                    data=json.dumps(data))
                response.raise_for_status()
                old_decision = response.json()
                if decision != old_decision:
                    decision.update({
                        'subject': [task],
                        'decision_context': decision_context,
                        'product_version': product_version,
                        'previous': old_decision,
                    })
                    log.debug('Emitted a fedmsg, %r, on the "%s" topic', decision,
                              'greenwave.decision.update')
                    fedmsg.publish(topic='decision.update', msg=decision)

    def _invalidate_cache(self, message):
        """
        Process the given message and delete cache keys as necessary.

        Args:
            message (munch.Munch): A fedmsg about a new result or waiver.
        """
        msg = copy.deepcopy(message['msg'])
        task = msg['task']
        del task['name']
        # here, task is {"item": "nodejs-ansi-black-0.1.1-1.fc28", "type": "koji_build" }
        namespace = None
        fn = greenwave.resources.retrieve_results
        key = greenwave.cache.key_generator(namespace, fn)(task)
        if not self.cache.get(key):
            log.debug("No cache value found for %r", key)
        else:
            log.debug("Invalidating cache for %r", key)
            self.cache.delete(key)
