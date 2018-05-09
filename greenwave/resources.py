# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import json
import requests
import urllib3.exceptions

import urlparse
import xmlrpclib
from flask import current_app
from werkzeug.exceptions import BadGateway

from greenwave.cache import cached
import greenwave.utils
import greenwave.policies

requests_session = requests.Session()


@cached
@greenwave.utils.retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_rev_from_koji(nvr):
    """ Retrieve cached rev from koji using the nrv """
    proxy = xmlrpclib.ServerProxy(current_app.config['KOJI_BASE_URL'])
    build = proxy.getBuild(nvr)

    if not build:
        raise BadGateway("Found %s when looking for %s at %s" % (
            build, nvr, current_app.config['KOJI_BASE_URL']))

    try:
        url = urlparse.urlparse(build['extra']['source']['original_url'])
        if not url.scheme.startswith('git'):
            raise BadGateway('Error occurred looking for the "rev" in koji.')
        return url.fragment
    except Exception:
        raise BadGateway('Error occurred looking for the "rev" in koji.')


@cached
def retrieve_yaml_remote_original_spec_nvr_rule(rev, pkg_name):
    """ Retrieve cached gating.yaml content for a given rev. """
    data = {
        "DIST_GIT_BASE_URL": current_app.config['DIST_GIT_BASE_URL'],
        "pkg_name": pkg_name,
        "rev": rev
    }
    url = current_app.config['DIST_GIT_URL_TEMPLATE'].format(**data)
    response = requests_session.request('HEAD', url,
                                        headers={'Content-Type': 'application/json'},
                                        timeout=60)
    if response.status_code == 404:
        return greenwave.policies.RuleSatisfied()
    elif response.status_code != 200:
        raise BadGateway('Error occurred looking for gating.yaml file in the dist-git repo.')

    # gating.yaml found...
    response = requests_session.request('GET', url,
                                        headers={'Content-Type': 'application/json'},
                                        timeout=60)
    response.raise_for_status()
    return response.content


@cached
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
@greenwave.utils.retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_waivers(product_version, items):
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']

    data = {
        'product_version': product_version,
        'results': [{"subject": item} for item in items]
    }

    response = requests_session.post(
        current_app.config['WAIVERDB_API_URL'] + '/waivers/+by-subjects-and-testcases',
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data),
        verify=verify,
        timeout=timeout)
    response.raise_for_status()
    return response.json()['data']


# NOTE - not cached.
@greenwave.utils.retry(timeout=300, interval=30, wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_decision(greenwave_url, data):
    # TODO - get REQUESTS_TIMEOUT and REQUESTS_VERIFY here somehow.  This is usually
    # called from the fedmsg-hub backend which doesn't have access to the flask
    # application context.  We need to load the app context and config at backend
    # startup to clean this up.
    headers = {'Content-Type': 'application/json'}
    response = requests_session.post(greenwave_url, headers=headers, data=json.dumps(data))
    response.raise_for_status()
    return response.json()
