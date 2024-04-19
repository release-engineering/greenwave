# SPDX-License-Identifier: GPL-2.0+

from json import loads
from unittest.mock import patch

from requests.exceptions import ConnectionError

from greenwave.request_session import get_requests_session


@patch("requests.adapters.HTTPAdapter.send")
def test_retry_handler(mocked_request):
    msg_text = "It happens..."
    mocked_request.side_effect = ConnectionError(msg_text)
    session = get_requests_session()
    resp = session.get("http://localhost.localdomain")
    assert resp.status_code == 502
    assert loads(resp.content) == {"message": msg_text}
