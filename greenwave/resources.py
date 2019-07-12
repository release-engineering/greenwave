# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import logging
import re
import json
from io import BytesIO
import tarfile
import subprocess

from urllib.parse import urlparse
import xmlrpc.client
from flask import current_app
from werkzeug.exceptions import BadGateway

from greenwave.cache import cached
from greenwave.request_session import get_requests_session

log = logging.getLogger(__name__)

requests_session = get_requests_session()


class BaseRetriever:
    def __init__(self, ignore_ids, when, timeout, verify, url):
        self.ignore_ids = ignore_ids
        self.timeout = timeout
        self.verify = verify
        self.url = url

        if when:
            self.since = '1900-01-01T00:00:00.000000,{}'.format(when)
        else:
            self.since = None

    def retrieve(self, *args, **kwargs):
        items = self._retrieve_all(*args, **kwargs)
        return [item for item in items if item['id'] not in self.ignore_ids]

    def _retrieve_data(self, params):
        response = self._make_request(params, verify=self.verify, timeout=self.timeout)
        response.raise_for_status()
        return response.json()['data']


class ResultsRetriever(BaseRetriever):
    """
    Retrieves results from cache or ResultsDB.
    """
    def __init__(self, **args):
        super().__init__(**args)
        self.cache = {}

    def _retrieve_all(self, subject_type, subject_identifier, testcase=None, scenarios=None):
        # Get test case result from cache if all test case results were already
        # retrieved for given subject type/ID.
        cache_key = (subject_type, subject_identifier, scenarios)
        if testcase and cache_key in self.cache:
            for result in self.cache[cache_key]:
                if result['testcase']['name'] == testcase:
                    return [result]
            return []

        params = {
            '_distinct_on': 'scenario,system_architecture'
        }
        if self.since:
            params.update({'since': self.since})
        if testcase:
            params.update({'testcases': testcase})
        if scenarios:
            params.update({'scenario': ','.join(scenarios)})

        results = []
        if subject_type == 'koji_build':
            params['type'] = 'koji_build,brew-build'
            params['item'] = subject_identifier
            results = self._retrieve_data(params)

            del params['type']
            del params['item']
            params['original_spec_nvr'] = subject_identifier
            results.extend(self._retrieve_data(params))
        elif subject_type == 'compose':
            params['productmd.compose.id'] = subject_identifier
            results = self._retrieve_data(params)
        else:
            params['type'] = subject_type
            params['item'] = subject_identifier
            results = self._retrieve_data(params)

        if not testcase:
            self.cache[cache_key] = results

        return results

    def _make_request(self, params, **request_args):
        return requests_session.get(
            self.url + '/results/latest',
            params=params,
            **request_args)


class WaiversRetriever(BaseRetriever):
    """
    Retrieves waivers from WaiverDB.
    """
    def _retrieve_all(self, filters):
        if self.since:
            for filter_ in filters:
                filter_.update({'since': self.since})
        waivers = self._retrieve_data(filters)
        return [waiver for waiver in waivers if waiver['waived']]

    def _make_request(self, params, **request_args):
        return requests_session.post(
            self.url + '/waivers/+filtered',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'filters': params}),
            **request_args)


@cached
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
    # Retry thrice if TimeoutExpired exception is raised
    MAX_RETRY = 3
    for _ in range(MAX_RETRY):
        try:
            git_archive = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error_output = git_archive.communicate(timeout=30)
            break
        except subprocess.TimeoutExpired:
            git_archive.kill()
            continue

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


# NOTE - not cached.
def retrieve_decision(greenwave_url, data):
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    headers = {'Content-Type': 'application/json'}
    response = requests_session.post(greenwave_url, headers=headers, data=json.dumps(data),
                                     timeout=timeout, verify=verify)
    response.raise_for_status()
    return response.json()
