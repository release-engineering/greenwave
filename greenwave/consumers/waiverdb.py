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
        self.topic = [
            prefix + '.' + env + '.waiver.new',
        ]
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
        result_id = msg['result_id']
        product_version = msg['product_version']
        config = load_config()
        timeout = config['REQUESTS_TIMEOUT']
        # Get the waived result to figure out the item
        response = requests_session.get(
            config['RESULTSDB_API_URL'] + '/results/%d' % result_id,
            timeout=timeout)
        response.raise_for_status()
        testcase = response.json()['testcase']['name']
        # In ResultsDB, 'data' is key -> list of strings.
        # But in Greenwave, we only deal in key -> string.
        # This is... iffy and might need cleaning up?
        item = {k: v[0] for k, v in response.json()['data'].items()}
        for policy in config['policies']:
            for rule in policy.rules:
                if rule.test_case_name == testcase:
                    data = {
                        'decision_context': policy.decision_context,
                        'product_version': product_version,
                        'subject': [item],
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
                        msg = decision
                        decision.update({
                            'subject': [item],
                            'decision_context': policy.decision_context,
                            'product_version': product_version,
                            'previous': old_decision,
                        })
                        log.debug('Emitted a fedmsg, %r, on the "%s" topic', msg,
                                  'greenwave.decision.update')
                        fedmsg.publish(topic='decision.update', msg=msg)
