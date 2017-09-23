# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
The "cache handler".

This module is responsible for listening for new results from ResultsDB (and
eventually waiverdb also). When a new result or waiver is received, this code
will lookup any possible cache values we have for that item and destroy them --
invalidate them.

https://pagure.io/greenwave/issue/77
"""

import logging
import requests
import dogpile.cache
import fedmsg.consumers

import greenwave.cache
import greenwave.resources

requests_session = requests.Session()


log = logging.getLogger(__name__)


class CacheInvalidatorExtraordinaire(fedmsg.consumers.FedmsgConsumer):
    """
    Handle a new result or waiver.

    Attributes:
        topic (list): A list of strings that indicate which fedmsg topics this consumer listens to.
    """

    config_key = 'cache_invalidator'

    def __init__(self, hub, *args, **kwargs):
        """
        Initialize the CacheInvalidatorExtraordinaire, subscribing it to the appropriate topics.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub from which this handler is consuming
                messages. It is used to look up the hub config.
        """

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = [
            prefix + '.' + env + '.taskotron.result.new',
            # Not ready to handle waivers yet...
            #prefix + '.' + env + '.waiver.new',
        ]
        self.fedmsg_config = fedmsg.config.load_config()
        super(CacheInvalidatorExtraordinaire, self).__init__(hub, *args, **kwargs)
        log.info('Greenwave cache invalidator listening on:\n'
                 '%r' % self.topic)

        # Initialize the cache.
        self.cache = dogpile.cache.make_region()
        self.cache.configure(**hub.config['greenwave_cache'])

    def consume(self, message):
        """
        Process the given message and delete cache keys as necessary.

        Args:
            message (munch.Munch): A fedmsg about a new result or waiver.
        """
        log.debug('Processing message "{0}"'.format(message))
        msg = message['msg']
        task = msg['task']
        del task['name']
        # here, task is {"item": "nodejs-ansi-black-0.1.1-1.fc28", "type": "koji_build" }
        namespace = None
        fn = greenwave.resources.retrieve_results
        key = greenwave.cache.key_generator(namespace, fn)(task)
        if not self.cache.get(key):
            raise KeyError(key)
        self.cache.delete(key)
