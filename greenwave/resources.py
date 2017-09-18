# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import requests
from flask import current_app

from greenwave.cache import cache, key_generator

requests_session = requests.Session()


@cache.cache_on_arguments(function_key_generator=key_generator)
def retrieve_results(item):
    """ Retrieve cached results from resultsdb for a given item. """
    # XXX make this more efficient than just fetching everything
    params = item.copy()
    params.update({'limit': '1000'})
    timeout = current_app.config['REQUESTS_TIMEOUT']
    response = requests_session.get(
        current_app.config['RESULTSDB_API_URL'] + '/results',
        params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()['data']


# NOTE - not cached, for now.
def retrieve_waivers(product_version, results):
    timeout = current_app.config['REQUESTS_TIMEOUT']
    response = requests_session.get(
        current_app.config['WAIVERDB_API_URL'] + '/waivers/',
        params={'product_version': product_version,
                'result_id': ','.join(str(result['id']) for result in results)},
        timeout=timeout)
    response.raise_for_status()
    return response.json()['data']
