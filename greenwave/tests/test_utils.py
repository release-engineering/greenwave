
# SPDX-License-Identifier: GPL-2.0+

import pytest
import urllib3

import json

from requests import ConnectionError, ConnectTimeout, Timeout
from werkzeug.exceptions import InternalServerError

import greenwave.app_factory
from greenwave.utils import json_error


@pytest.mark.parametrize(('error, expected_status_code,'
                          'expected_error_message_part'), [
    (ConnectionError('ERROR'), 502, 'ERROR'),
    (ConnectTimeout('TIMEOUT'), 502, 'TIMEOUT'),
    (Timeout('TIMEOUT'), 504, 'TIMEOUT'),
    (InternalServerError(), 500, 'The server encountered an internal error'),
    (urllib3.exceptions.MaxRetryError(
        'MAX_RETRY', '.../gating.yaml'), 502, ('There was an error retrieving the '
                                               'gating.yaml file at .../gating.yaml'))
])
def test_json_connection_error(error, expected_status_code,
                               expected_error_message_part):
    app = greenwave.app_factory.create_app()
    with app.app_context():
        with app.test_request_context():
            r = json_error(error)
            data = json.loads(r.get_data())
            assert r.status_code == expected_status_code
            assert expected_error_message_part in data['message']
