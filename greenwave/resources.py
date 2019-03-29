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
from io import BytesIO
import tarfile
import subprocess

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

    def retrieve_latest(self, subject_type, subject_identifier):
        """
        Return generator over latest results.
        """
        params = {}
        return self._retrieve_helper(params, subject_type, subject_identifier, latest=True)

    def retrieve(self, subject_type, subject_identifier, testcase=None):
        """
        Return generator over results.
        """
        for result in self._retrieve_all(subject_type, subject_identifier, testcase):
            if result['id'] not in self.ignore_results:
                yield result

    def _retrieve_all(self, subject_type, subject_identifier, testcase):
        cache_key = results_cache_key(
            subject_type, subject_identifier, testcase)

        cached_results = self.cache.get(cache_key)
        if not isinstance(cached_results, CachedResults):
            cached_results = CachedResults()

        for result in cached_results.results:
            yield result

        while cached_results.can_fetch_more:
            cached_results.last_page += 1
            params = {
                'limit': 1,
                'page': cached_results.last_page,
            }

            if testcase:
                params['testcases'] = testcase
            results = self._retrieve_helper(params, subject_type, subject_identifier)
            cached_results.results.extend(results)
            cached_results.can_fetch_more = bool(results)
            self.cache.set(cache_key, cached_results)
            for result in results:
                yield result

    def _make_request(self, params, latest=False):
        request_url = self.url + '/results'
        if latest:
            request_url += '/latest'
            # we need to consider also the scenario
            params['_distinct_on'] = 'scenario'
        response = requests_session.get(
            request_url, params=params, verify=self.verify, timeout=self.timeout)
        response.raise_for_status()
        return response.json()['data']

    def _retrieve_helper(self, params, subject_type, subject_identifier, latest=False):
        results = []
        if subject_type == 'koji_build':
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._make_request(params=params, latest=latest)

            params['type'] = 'brew-build'
            results.extend(self._make_request(params=params, latest=latest))

            del params['type']
            del params['item']
            params['original_spec_nvr'] = subject_identifier
            results.extend(self._make_request(params=params, latest=latest))
        elif subject_type == 'compose':
            params['productmd.compose.id'] = subject_identifier
            results = self._make_request(params=params, latest=latest)
        else:
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._make_request(params=params, latest=latest)

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
    if current_app.config['DIST_GIT_BASE_URL'].startswith('git://'):
        return _retrieve_yaml_remote_rule_git_archive(rev, pkg_name, pkg_namespace)
    else:
        return _retrieve_yaml_remote_rule_web(rev, pkg_name, pkg_namespace)


_retrieve_gating_yaml_error = 'Error occurred looking for gating.yaml file in the dist-git repo.'


def _retrieve_yaml_remote_rule_web(rev, pkg_name, pkg_namespace):
    """ Retrieve the gating.yaml file from the dist-git web UI. """
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
        raise BadGateway(_retrieve_gating_yaml_error)

    # gating.yaml found...
    response = requests_session.request('GET', url,
                                        headers={'Content-Type': 'application/json'},
                                        timeout=60)
    response.raise_for_status()
    return response.content


def _retrieve_yaml_remote_rule_git_archive(rev, pkg_name, pkg_namespace):
    """ Retrieve the gating.yaml file from a dist-git repo using git archive. """
    dist_git_base_url = current_app.config['DIST_GIT_BASE_URL'].rstrip('/')
    dist_git_url = f'{dist_git_base_url}/{pkg_namespace}/{pkg_name}'
    cmd = ['git', 'archive', f'--remote={dist_git_url}', rev, 'gating.yaml']
    git_archive = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error_output = git_archive.communicate()

    if git_archive.returncode != 0:
        error_output = error_output.decode('utf-8')
        if 'path not found' in error_output:
            return None

        cmd_str = ', '.join(cmd)
        log.error('The following exception occurred while running "%s": %s', cmd_str, error_output)
        raise BadGateway(_retrieve_gating_yaml_error)

    # Convert the output to a file-like object with BytesIO, then tar can read it
    # in memory rather than writing it to a file first
    gating_yaml_archive = tarfile.open(fileobj=BytesIO(output))
    gating_yaml = gating_yaml_archive.extractfile('gating.yaml').read().decode('utf-8')
    return gating_yaml


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
