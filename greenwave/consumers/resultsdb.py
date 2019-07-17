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

from greenwave.consumers.consumer import Consumer

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
    elif toparse.startswith('el') and len(toparse) > 2 and toparse[2].isdigit():
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


def _subject_product_version(subject_identifier, subject_type, koji_proxy=None):
    if subject_type == 'koji_build':
        try:
            _, _, release = subject_identifier.rsplit('-', 2)
            _, short_prod_version = release.rsplit('.', 1)
            return _guess_product_version(short_prod_version, koji_build=True)
        except (KeyError, ValueError):
            pass

    if subject_type == "compose":
        return _guess_product_version(subject_identifier)

    if subject_type == "redhat-module":
        return "rhel-8"

    if koji_proxy:
        try:
            build = koji_proxy.getBuild(subject_identifier)
            if build:
                target = koji_proxy.getTaskRequest(build['task_id'])[1]
                return _guess_product_version(target, koji_build=True)
        except KeyError:
            pass
        except xmlrpc.client.Fault:
            pass


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

        def _decode(value):
            """ Decode either a string or a list of strings. """
            if value and len(value) == 1:
                value = value[0]
            return value

        _type = _decode(data.get('type'))
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
            yield ('compose', _decode(data['productmd.compose.id']))
        elif _type == 'compose':
            pass
        elif 'original_spec_nvr' in data:
            nvr = _decode(data['original_spec_nvr'])
            # when the pipeline ignores a package, which happens
            # *a lot*, we get a message with an 'original_spec_nvr'
            # key with an empty value; let's not try and handle this
            if nvr:
                yield ('koji_build', nvr)
        elif _type == 'brew-build':
            yield ('koji_build', _decode(data['item']))
        elif 'item' in data and _type:
            yield (_type, _decode(data['item']))

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

        for subject_type, subject_identifier in self.announcement_subjects(message):
            log.debug('Considering subject %s: %r', subject_type, subject_identifier)

            product_version = _subject_product_version(
                subject_identifier, subject_type, self.koji_proxy)

            self._publish_decision_change(
                submit_time=submit_time,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                testcase=testcase,
                product_version=product_version,
                publish_testcase=False,
            )
