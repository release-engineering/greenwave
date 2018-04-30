# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import json

import requests
import urllib3.exceptions

from flask import current_app

from greenwave.cache import cached
from greenwave.utils import retry

requests_session = requests.Session()


@cached
@retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_results(item):
    """ Retrieve cached results from resultsdb for a given item. """
    # XXX make this more efficient than just fetching everything
    params = item.copy()
    params.update({'limit': '1000'})
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    response = requests_session.get(
        current_app.config['RESULTSDB_API_URL'] + '/results',
        params=params, verify=verify, timeout=timeout)
    response.raise_for_status()
    return response.json()['data']


# NOTE - not cached, for now.
@retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_waivers(product_version, item):
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    data = {
        'product_version': product_version,
        'results': [{"subject": item}]
    }
    response = requests_session.post(
        current_app.config['WAIVERDB_API_URL'] + '/waivers/+by-subjects-and-testcases',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data),
        verify=verify,
        timeout=timeout)
    response.raise_for_status()
    return response.json()['data']
