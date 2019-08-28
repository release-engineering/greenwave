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

from greenwave.consumers.consumer import Consumer
from greenwave.product_versions import subject_product_version

import xmlrpc.client

log = logging.getLogger(__name__)


def _unpack_value(value):
    """
    If value is list with single element, returns the element, otherwise
    returns the value.
    """
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value


def _get_brew_task_id(msg):
    data = msg.get('data')
    if not data:
        return None

    task_id = _unpack_value(data.get('brew_task_id'))
    try:
        return int(task_id)
    except (ValueError, TypeError):
        return None


class ResultsDBHandler(Consumer):
    """
    Handle a new result.

    Attributes:
        topic (list): A list of strings that indicate which fedmsg topics this consumer listens to.
    """

    config_key = 'resultsdb_handler'
    hub_config_prefix = 'resultsdb_'
    default_topic = 'taskotron.result.new'
    monitor_labels = {'handler': 'resultsdb'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        koji_base_url = self.flask_app.config['KOJI_BASE_URL']
        if koji_base_url:
            self.koji_proxy = xmlrpc.client.ServerProxy(koji_base_url)
        else:
            self.koji_proxy = None

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

        _type = _unpack_value(data.get('type'))
        # note: it is *intentional* that we do not handle old format
        # compose-type messages, because it is impossible to reliably
        # produce a decision from these. compose decisions can only be
        # reliably made from new format messages, where we can rely on
        # productmd.compose.id being available. See:
        # https://pagure.io/greenwave/issue/122
        # https://pagure.io/taskotron/resultsdb/issue/92
        # https://pagure.io/taskotron/resultsdb/pull-request/101
        # https://pagure.io/greenwave/pull-request/262#comment-70350
        if 'productmd.compose.id' in data:
            yield ('compose', _unpack_value(data['productmd.compose.id']))
        elif _type == 'compose':
            pass
        elif 'original_spec_nvr' in data:
            nvr = _unpack_value(data['original_spec_nvr'])
            # when the pipeline ignores a package, which happens
            # *a lot*, we get a message with an 'original_spec_nvr'
            # key with an empty value; let's not try and handle this
            if nvr:
                yield ('koji_build', nvr)
        elif _type == 'brew-build':
            yield ('koji_build', _unpack_value(data['item']))
        elif 'item' in data and _type:
            yield (_type, _unpack_value(data['item']))

    def _consume_message(self, message):
        msg = message['msg']

        try:
            testcase = msg['testcase']['name']
        except KeyError:
            testcase = msg['task']['name']

        try:
            submit_time = msg['submit_time']
        except KeyError:
            submit_time = msg['result']['submit_time']

        brew_task_id = _get_brew_task_id(msg)

        for subject_type, subject_identifier in self.announcement_subjects(message):
            log.debug('Considering subject %s: %r', subject_type, subject_identifier)

            product_version = subject_product_version(
                subject_identifier,
                subject_type,
                self.koji_proxy,
                brew_task_id,
            )

            self._publish_decision_change(
                submit_time=submit_time,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                testcase=testcase,
                product_version=product_version,
                publish_testcase=False,
            )
