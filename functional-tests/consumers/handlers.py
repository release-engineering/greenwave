# SPDX-License-Identifier: GPL-2.0+

import mock

from greenwave.config import TestingConfig


def create_handler(handler_class, topic, greenwave_server, cache_config=None):
    hub = mock.MagicMock()
    hub.config = {
        'environment': 'environment',
        'topic_prefix': 'topic_prefix',
    }

    config = TestingConfig()
    config.GREENWAVE_API_URL = greenwave_server + '/api/v1.0'
    if cache_config:
        config.CACHE = cache_config

    handler = handler_class(hub, config=config)
    assert handler.topic == [topic]
    return handler
