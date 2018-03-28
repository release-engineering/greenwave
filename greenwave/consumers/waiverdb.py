# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
The "waiverdb handler".

This module is responsible for listening new waivers from WaiverDB. When a new
waiver is received, Greenwave will check all applicable policies for that waiver,
and if the new waiver causes the decision to change it will publish a message
to the message bus about the newly satisfied/unsatisfied policy.
"""

import logging
import requests
import json
import fedmsg.consumers

from greenwave.utils import load_config

requests_session = requests.Session()


log = logging.getLogger(__name__)


class WaiverDBHandler(fedmsg.consumers.FedmsgConsumer):
    """
    Handle a new waiver.

    Attributes:
        topic (list): A list of strings that indicate which fedmsg topics this consumer listens to.
    """

    config_key = 'waiverdb_handler'

    def __init__(self, hub, *args, **kwargs):
        """
        Initialize the WaiverDBHandler, subscribing it to the appropriate topics.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub from which this handler is consuming
                messages. It is used to look up the hub config.
        """

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        suffix = hub.config.get('waiverdb_topic_suffix', 'waiver.new')
        self.topic = ['.'.join([prefix, env, suffix])]
        self.fedmsg_config = fedmsg.config.load_config()

        super(WaiverDBHandler, self).__init__(hub, *args, **kwargs)
        log.info('Greenwave waiverdb handler listening on: %s', self.topic)

    def consume(self, message):
        """
        Process the given message and publish a message if the decision is changed.

        Args:
            message (munch.Munch): A fedmsg about a new waiver.
        """
        message = message.get('body', message)
        log.debug('Processing message "%s"', message)
        msg = message['msg']

        product_version = msg['product_version']
        config = load_config()
        testcase = msg['testcase']
        for policy in config['policies']:
            for rule in policy.rules:
                if rule.test_case_name == testcase:
                    data = {
                        'decision_context': policy.decision_context,
                        'product_version': product_version,
                        'subject': msg['subject']
                    }
                    response = requests_session.post(
                        self.fedmsg_config['greenwave_api_url'] + '/decision',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(data))
                    decision = response.json()

                    # get old decision
                    data.update({
                        'ignore_waiver': [msg['id']],
                    })
                    response = requests_session.post(
                        self.fedmsg_config['greenwave_api_url'] + '/decision',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(data))
                    response.raise_for_status()
                    old_decision = response.json()

                    if decision != old_decision:
                        subject = [dict((str(k), str(v)) for k, v in item.items())
                                   for item in msg['subject']]
                        msg = decision
                        decision.update({
                            'subject': subject,
                            'testcase': testcase,
                            'decision_context': policy.decision_context,
                            'product_version': product_version,
                            'previous': old_decision,
                        })
                        log.debug('Emitted a fedmsg, %r, on the "%s" topic', msg,
                                  'greenwave.decision.update')
                        fedmsg.publish(topic='decision.update', msg=msg)
