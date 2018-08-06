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

from flask import current_app
import fedmsg.consumers
import requests

import greenwave.app_factory
import greenwave.cache
import greenwave.resources
from greenwave.api_v1 import subject_type_identifier_to_list


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

        self.flask_app = greenwave.app_factory.create_app()
        self.cache = self.flask_app.cache

        log.info('Greenwave resultsdb handler listening on: %s', self.topic)

    @staticmethod
    def announcement_subjects(message):
        """
        Yields pairs of (subject type, subject identifier) for announcement
        consideration from the message.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """

        try:
            data = message['msg']['data']  # New format
        except KeyError:
            data = message['msg']['task']  # Old format

        def _decode(value):
            """ Decode either a string or a list of strings. """
            if value and len(value) == 1:
                value = value[0]
            return value

        _type = _decode(data.get('type'))
        if _type == 'bodhi_update' and 'item' in data:
            yield ('bodhi_update', _decode(data['item']))
        if _type == 'compose' and 'item' in data:
            yield ('compose', _decode(data['item']))
        if 'productmd.compose.id' in data:
            yield ('compose', _decode(data['productmd.compose.id']))
        if (_type == 'koji_build' and 'item' in data or
                _type == 'brew-build' and 'item' in data or
                'original_spec_nvr' in data):
            if _type in ['koji_build', 'brew-build']:
                nvr = _decode(data['item'])
            else:
                nvr = _decode(data['original_spec_nvr'])
            yield ('koji_build', nvr)
            # If the result is for a build, it may also influence the decision
            # about any update which the build is part of.
            if current_app.config['BODHI_URL']:
                updateid = greenwave.resources.retrieve_update_for_build(nvr)
                if updateid is not None:
                    yield ('bodhi_update', updateid)

    def consume(self, message):
        """
        Process the given message and take action.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """
        message = message.get('body', message)
        log.debug('Processing message "%s"', message)

        try:
            testcase = message['msg']['testcase']['name']  # New format
        except KeyError:
            testcase = message['msg']['task']['name']  # Old format

        try:
            result_id = message['msg']['id']  # New format
        except KeyError:
            result_id = message['msg']['result']['id']  # Old format

        with self.flask_app.app_context():
            for subject_type, subject_identifier in self.announcement_subjects(message):
                log.debug('Considering subject %s: %r', subject_type, subject_identifier)
                self._invalidate_cache(subject_type, subject_identifier)
                self._publish_decision_changes(subject_type, subject_identifier,
                                               result_id, testcase)

    def _publish_decision_changes(self, subject_type, subject_identifier, result_id, testcase):
        """
        Process the given subject and publish a message if the decision is changed.

        Args:
            subject (munch.Munch): A subject argument, used to query greenwave.
            result_id (int): A result ID to ignore for comparison.
            testcase (munch.Munch): The name of a testcase to consider.
        """
        # Also need to apply policies for each build in the update.
        if subject_type == 'bodhi_update':
            subject_types = set([subject_type, 'koji_build'])
        else:
            subject_types = set([subject_type])

        # Build a set of all policies which might apply to this new results
        applicable_policies = set()
        for policy in current_app.config['policies']:
            if policy.subject_type in subject_types:
                testcases = (
                    getattr(rule, 'test_case_name', None)
                    for rule in policy.rules)

                if testcase in testcases:
                    applicable_policies.add(policy)

        log.debug("messaging: found %i applicable policies of %i for testcase %r",
                  len(applicable_policies), len(current_app.config['policies']), testcase)

        # Given all of our applicable policies, build a map of all decision
        # context we know about, and which product versions they relate to.
        decision_contexts = collections.defaultdict(set)
        for policy in applicable_policies:
            versions = set(policy.product_versions)
            decision_contexts[policy.decision_context].update(versions)
        log.debug("messaging: found %i decision contexts", len(decision_contexts))

        # For every context X version combination, ask greenwave if this new
        # result pushes any decisions over a threshold.
        for decision_context in sorted(decision_contexts.keys()):
            product_versions = decision_contexts[decision_context]
            for product_version in sorted(product_versions):
                greenwave_url = self.fedmsg_config['greenwave_api_url'] + '/decision'

                data = {
                    'decision_context': decision_context,
                    'product_version': product_version,
                    'subject_type': subject_type,
                    'subject_identifier': subject_identifier,
                }

                try:
                    decision = greenwave.resources.retrieve_decision(greenwave_url, data)

                    # get old decision
                    data.update({
                        'ignore_result': [result_id],
                    })
                    old_decision = greenwave.resources.retrieve_decision(greenwave_url, data)
                except requests.exceptions.HTTPError as e:
                    log.exception('Failed to retrieve decision for data=%s, error: %s', data, e)
                    continue

                if decision == old_decision:
                    log.debug('Skipped emitting fedmsg, decision did not change: %s', decision)
                else:
                    decision.update({
                        'subject_type': subject_type,
                        'subject_identifier': subject_identifier,
                        # subject is for backwards compatibility only:
                        'subject': subject_type_identifier_to_list(subject_type,
                                                                   subject_identifier),
                        'decision_context': decision_context,
                        'product_version': product_version,
                        'previous': old_decision,
                    })
                    log.debug('Emitted a fedmsg, %r, on the "%s" topic', decision,
                              'greenwave.decision.update')
                    fedmsg.publish(topic='decision.update', msg=decision)

    def _invalidate_cache(self, subject_type, subject_identifier):
        """
        Process the given subject and delete cache keys as necessary.

        Args:
            subject_type (str): A subject type, used to query greenwave.
            subject_identifier (str): A subject identifier, used to query greenwave.
        """
        namespace = None
        fn = greenwave.resources.retrieve_results
        key = greenwave.cache.key_generator(namespace, fn)(subject_type, subject_identifier)
        if not self.cache.get(key):
            log.debug("No cache value found for %r", key)
        else:
            log.debug("Invalidating cache for %r", key)
            self.cache.delete(key)
