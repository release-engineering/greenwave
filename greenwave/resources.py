# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import logging
import re
import json
import requests
import urllib3.exceptions

from urllib.parse import urlparse
import xmlrpc.client
from flask import current_app
from werkzeug.exceptions import BadGateway

from greenwave.cache import cached
import greenwave.utils

log = logging.getLogger(__name__)

requests_session = requests.Session()


class CachedResults(object):
    """
    Results data in cache.
    """
    def __init__(self):
        self.results = []
        self.can_fetch_more = True
        self.last_page = -1


def results_cache_key(subject_type, subject_identifier, testcase):
    """
    Returns cache key for results for given parameters.
    """
    return "greenwave.resources:CachedResults|{} {} {}".format(
        subject_type, subject_identifier, testcase)


class ResultsRetriever(object):
    """
    Retrieves results from cache or ResultsDB.
    """
    def __init__(self, cache, ignore_results, timeout, verify, url):
        self.cache = cache
        self.ignore_results = ignore_results
        self.timeout = timeout
        self.verify = verify
        self.url = url

    def retrieve(self, subject_type, subject_identifier, testcase=None):
        """
        Return generator over results.
        """
        for result in self._retrieve_helper(subject_type, subject_identifier, testcase):
            if result['id'] not in self.ignore_results:
                yield result

    def _retrieve_helper(self, subject_type, subject_identifier, testcase):
        cache_key = results_cache_key(
            subject_type, subject_identifier, testcase)

        cached_results = self.cache.get(cache_key)
        if not isinstance(cached_results, CachedResults):
            cached_results = CachedResults()

        for result in cached_results.results:
            yield result

        while cached_results.can_fetch_more:
            cached_results.last_page += 1
            results = self._retrieve_page(
                cached_results.last_page, subject_type, subject_identifier,
                testcase)
            cached_results.results.extend(results)
            cached_results.can_fetch_more = bool(results)
            self.cache.set(cache_key, cached_results)
            for result in results:
                yield result

    def _make_request(self, params):
        response = requests_session.get(
            self.url + '/results', params=params, verify=self.verify, timeout=self.timeout)
        response.raise_for_status()
        return response.json()['data']

    def _retrieve_page(self, page, subject_type, subject_identifier, testcase):
        params = {
            'limit': 1,
            'page': page,
        }

        if testcase:
            params['testcases'] = testcase

        results = []
        if subject_type == 'bodhi_update':
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._make_request(params=params)
        elif subject_type == 'koji_build':
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._make_request(params=params)

            params['type'] = 'brew-build'
            results.extend(self._make_request(params=params))

            del params['type']
            del params['item']
            params['original_spec_nvr'] = subject_identifier
            results.extend(self._make_request(params=params))
        elif subject_type == 'compose':
            params['productmd.compose.id'] = subject_identifier
            results = self._make_request(params=params)

            del params['productmd.compose.id']

            params['type'] = 'compose'
            params['item'] = subject_identifier
            results.extend(self._make_request(params=params))
        elif subject_type == 'component-version' or subject_type == 'redhat-module':
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._make_request(params=params)

        else:
            raise RuntimeError('Unhandled subject type %r' % subject_type)

        return results


@cached
@greenwave.utils.retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_scm_from_koji(nvr):
    """ Retrieve cached rev and namespace from koji using the nvr """
    koji_url = current_app.config['KOJI_BASE_URL']
    proxy = xmlrpc.client.ServerProxy(koji_url)
    build = proxy.getBuild(nvr)
    return retrieve_scm_from_koji_build(nvr, build, koji_url)


def retrieve_scm_from_koji_build(nvr, build, koji_url):
    if not build:
        raise BadGateway(
            'Failed to find Koji build for "{}" at "{}"'.format(nvr, koji_url))

    source = build.get('source')
    if not source:
        raise BadGateway(
            'Failed to retrieve SCM URL from Koji build "{}" at "{}" '
            '(expected SCM URL in "source" attribute)'
            .format(nvr, koji_url))

    url = urlparse(source)

    path_components = url.path.rsplit('/', 2)
    if len(path_components) < 3:
        namespace = ""
    else:
        namespace = path_components[-2]

    rev = url.fragment
    if not rev:
        raise BadGateway(
            'Failed to parse SCM URL "{}" from Koji build "{}" at "{}" '
            '(missing URL fragment with SCM revision information)'
            .format(source, nvr, koji_url))

    pkg_name = url.path.split('/')[-1]
    pkg_name = re.sub(r'\.git$', '', pkg_name)
    return namespace, pkg_name, rev


@cached
def retrieve_yaml_remote_rule(rev, pkg_name, pkg_namespace):
    """ Retrieve cached gating.yaml content for a given rev. """
    data = {
        "DIST_GIT_BASE_URL": (current_app.config['DIST_GIT_BASE_URL'].rstrip('/') +
                              ('/' if pkg_namespace else '')),
        "pkg_namespace": pkg_namespace,
        "pkg_name": pkg_name,
        "rev": rev
    }
    url = current_app.config['DIST_GIT_URL_TEMPLATE'].format(**data)
    response = requests_session.request('HEAD', url,
                                        headers={'Content-Type': 'application/json'},
                                        timeout=60)
    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise BadGateway('Error occurred looking for gating.yaml file in the dist-git repo.')

    # gating.yaml found...
    response = requests_session.request('GET', url,
                                        headers={'Content-Type': 'application/json'},
                                        timeout=60)
    response.raise_for_status()
    return response.content


# NOTE - not cached, for now.
@greenwave.utils.retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_waivers(product_version, subject_type, subject_identifiers):
    if not subject_identifiers:
        return []

    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    filters = [{
        'product_version': product_version,
        'subject_type': subject_type,
        'subject_identifier': subject_identifier,
    } for subject_identifier in subject_identifiers]
    response = requests_session.post(
        current_app.config['WAIVERDB_API_URL'] + '/waivers/+filtered',
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'filters': filters}),
        verify=verify,
        timeout=timeout)
    response.raise_for_status()
    return response.json()['data']


# NOTE - not cached.
@greenwave.utils.retry(timeout=300, interval=30, wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_decision(greenwave_url, data):
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    headers = {'Content-Type': 'application/json'}
    response = requests_session.post(greenwave_url, headers=headers, data=json.dumps(data),
                                     timeout=timeout, verify=verify)
    response.raise_for_status()
    return response.json()
