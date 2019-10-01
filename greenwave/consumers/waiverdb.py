# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
The "waiverdb handler".

This module is responsible for listening new waivers from WaiverDB. When a new
waiver is received, Greenwave will check all applicable policies for that waiver,
and if the new waiver causes the decision to change it will publish a message
to the message bus about the newly satisfied/unsatisfied policy.
"""

from greenwave.consumers.consumer import Consumer
from greenwave.subjects.factory import create_subject


class WaiverDBHandler(Consumer):
    """
    Handle a new waiver.

    Attributes:
        topic (list): A list of strings that indicate which fedmsg topics this consumer listens to.
    """

    config_key = 'waiverdb_handler'
    hub_config_prefix = 'waiverdb_'
    default_topic = 'waiver.new'
    monitor_labels = {'handler': 'waiverdb'}

    def _consume_message(self, message):
        msg = message['msg']

        product_version = msg['product_version']
        testcase = msg['testcase']
        subject = create_subject(msg['subject_type'], msg['subject_identifier'])
        submit_time = msg['timestamp']

        self._publish_decision_change(
            submit_time=submit_time,
            subject=subject,
            testcase=testcase,
            product_version=product_version,
            publish_testcase=True,
        )
