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
import requests
import json
import fedmsg.consumers

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
        log.info('Greenwave resultsdb handler listening on: %s', self.topic)

    def consume(self, message):
        """
        Process the given message and publish a message if the decision is changed.

        Args:
            message (munch.Munch): A fedmsg about a new result.
        """
        log.debug('Processing message "%s"', message)
        msg = message['msg']
        task = msg['task']
        testcase = task['name']
        del task['name']
        config = load_config()
        applicable_policies = []
        for policy in config['policies']:
            for rule in policy.rules:
                if rule.test_case_name == testcase:
                    applicable_policies.append(policy)
        for policy in applicable_policies:
            for product_version in policy.product_versions:
                data = {
                    'decision_context': policy.decision_context,
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
                    msg = decision
                    decision.update({
                        'subject': [task],
                        'decision_context': policy.decision_context,
                        'product_version': product_version,
                        'previous': old_decision,
                    })
                    log.debug('Emitted a fedmsg, %r, on the "%s" topic', msg,
                              'greenwave.decision.update')
                    fedmsg.publish(topic='greenwave.decision.update', msg=msg)
