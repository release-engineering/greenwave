# SPDX-License-Identifier: GPL-2.0+


def test_healthcheck(requests_session, greenwave_server):
    r = requests_session.get(greenwave_server + 'healthcheck')
    assert r.status_code == 200
    assert r.text == 'Health check OK'
