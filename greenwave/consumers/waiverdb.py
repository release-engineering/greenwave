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
import json

from flask import current_app
import fedmsg.consumers
import requests

import greenwave.app_factory
from greenwave.api_v1 import subject_type_identifier_to_list

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

        self.flask_app = greenwave.app_factory.create_app()
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
        testcase = msg['testcase']
        subject_type = msg['subject_type']
        subject_identifier = msg['subject_identifier']

        with self.flask_app.app_context():
            self._publish_decision_changes(subject_type, subject_identifier, msg['id'],
                                           product_version, testcase)
            if subject_type == 'koji_build' and current_app.config['BODHI_URL']:
                # If the waiver is for a build, it may also influence the decision
                # about any update which the build is part of.
                updateid = greenwave.resources.retrieve_update_for_build(subject_identifier)
                if updateid is not None:
                    self._publish_decision_changes('bodhi_update', updateid, msg['id'],
                                                   product_version, testcase)

    def _publish_decision_changes(self, subject_type, subject_identifier, waiver_id,
                                  product_version, testcase):
        for policy in self.flask_app.config['policies']:
            for rule in policy.rules:
                if getattr(rule, 'test_case_name', None) == testcase:
                    data = {
                        'decision_context': policy.decision_context,
                        'product_version': product_version,
                        'subject_type': subject_type,
                        'subject_identifier': subject_identifier,
                    }
                    response = requests_session.post(
                        self.fedmsg_config['greenwave_api_url'] + '/decision',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(data))

                    if not response.ok:
                        log.error(response.text)
                        continue

                    decision = response.json()

                    # get old decision
                    data.update({
                        'ignore_waiver': [waiver_id],
                    })
                    response = requests_session.post(
                        self.fedmsg_config['greenwave_api_url'] + '/decision',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(data))

                    if not response.ok:
                        log.error(response.text)
                        continue

                    old_decision = response.json()

                    if decision != old_decision:
                        msg = decision
                        decision.update({
                            'subject_type': subject_type,
                            'subject_identifier': subject_identifier,
                            # subject is for backwards compatibility only:
                            'subject': subject_type_identifier_to_list(subject_type,
                                                                       subject_identifier),
                            'testcase': testcase,
                            'decision_context': policy.decision_context,
                            'product_version': product_version,
                            'previous': old_decision,
                        })
                        log.debug('Emitted a fedmsg, %r, on the "%s" topic', msg,
                                  'greenwave.decision.update')
                        fedmsg.publish(topic='decision.update', msg=msg)
