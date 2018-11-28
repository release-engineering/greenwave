# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
The "resultsdb handler".

This module is responsible for listening new results from ResultsDB. When a new
result is received, Greenwave will check all applicable policies for that item,
and if the new result causes the decision to change it will publish a message
to the message bus about the newly satisfied/unsatisfied policy.
"""

import logging
import re

from flask import current_app
import fedmsg.consumers
import requests

import greenwave.app_factory
import greenwave.resources
from greenwave.api_v1 import subject_type_identifier_to_list
from greenwave.monitoring import publish_decision_exceptions_result_counter
from greenwave.policies import applicable_decision_context_product_version_pairs

import xmlrpc.client


log = logging.getLogger(__name__)


def _guess_product_version(toparse, koji_build=False):
    if toparse == 'rawhide' or toparse.startswith('Fedora-Rawhide'):
        return 'fedora-rawhide'

    product_version = None
    if toparse.startswith('f') and koji_build:
        product_version = 'fedora-'
    elif toparse.startswith('epel'):
        product_version = 'epel-'
    elif toparse.startswith('el'):
        product_version = 'rhel-'
    elif toparse.startswith('fc') or toparse.startswith('Fedora'):
        product_version = 'fedora-'

    if product_version:
        # seperate the prefix from the number
        result = list(filter(None, '-'.join(re.split(r'(\d+)', toparse)).split('-')))
        if len(result) >= 2:
            try:
                int(result[1])
                product_version += result[1]
                return product_version
            except ValueError:
                pass

    log.error("It wasn't possible to guess the product version")
    return None


def _subject_product_version(subject_identifier, subject_type):
    if subject_type == 'koji_build':
        try:
            short_prod_version = subject_identifier.split('.')[-1]
            return _guess_product_version(short_prod_version, koji_build=True)
        except KeyError:
            pass

    if subject_type == "compose":
        return _guess_product_version(subject_identifier)

    if subject_type == "redhat-module":
        return "rhel-8"

    koji_base_url = current_app.config['KOJI_BASE_URL']
    if koji_base_url:
        proxy = xmlrpc.client.ServerProxy(koji_base_url)
        try:
            build = proxy.getBuild(subject_identifier)
            if build:
                target = proxy.getTaskRequest(build['task_id'])[1]
                return _guess_product_version(target, koji_build=True)
        except KeyError:
            pass
        except xmlrpc.client.Fault:
            pass


def _invalidate_results_cache(
        cache, subject_type, subject_identifier, testcase):
    """
    Removes results for given parameters from cache.
    """
    key = greenwave.resources.results_cache_key(
        subject_type, subject_identifier, testcase)

    log.debug("Invalidating cache for %r", key)

    try:
        cache.delete(key)
    except KeyError:
        log.debug("No cache value found for %r", key)

    # Also invalidate query results without test case name.
    if testcase:
        _invalidate_results_cache(
            cache, subject_type, subject_identifier, testcase=None)


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
        if _type in ['bodhi_update', 'compose', 'component-version', 'redhat-module'] and (
                'item' in data):
            yield (_type, _decode(data['item']))
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
                _invalidate_results_cache(
                    self.cache, subject_type, subject_identifier, testcase)
                self._publish_decision_changes(subject_type, subject_identifier,
                                               result_id, testcase)

    @publish_decision_exceptions_result_counter.count_exceptions()
    def _publish_decision_changes(self, subject_type, subject_identifier, result_id, testcase):
        """
        Process the given subject and publish a message if the decision is changed.

        Args:
            subject (munch.Munch): A subject argument, used to query greenwave.
            result_id (int): A result ID to ignore for comparison.
            testcase (munch.Munch): The name of a testcase to consider.
        """
        product_version = _subject_product_version(subject_identifier, subject_type)
        policies = self.flask_app.config['policies']
        contexts_product_versions = applicable_decision_context_product_version_pairs(
            policies,
            subject_type=subject_type,
            subject_identifier=subject_identifier,
            testcase=testcase,
            product_version=product_version)

        for decision_context, product_version in sorted(contexts_product_versions):
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
