# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import logging
import re
import socket

from urllib.parse import urlparse
import xmlrpc.client
from flask import current_app
from werkzeug.exceptions import BadGateway, NotFound

from greenwave.cache import cached
from greenwave.request_session import get_requests_session

log = logging.getLogger(__name__)

requests_session = get_requests_session()


class BaseRetriever:
    def __init__(self, ignore_ids, when, url):
        self.ignore_ids = ignore_ids
        self.url = url

        if when:
            self.since = '1900-01-01T00:00:00.000000,{}'.format(when)
        else:
            self.since = None

    def retrieve(self, *args, **kwargs):
        items = self._retrieve_all(*args, **kwargs)
        return [item for item in items if item['id'] not in self.ignore_ids]

    def _retrieve_data(self, params):
        response = self._make_request(params)
        response.raise_for_status()
        return response.json()['data']


class ResultsRetriever(BaseRetriever):
    """
    Retrieves results from cache or ResultsDB.
    """

    def __init__(self, **args):
        super().__init__(**args)
        self.cache = {}

    def _retrieve_all(self, subject, testcase=None, scenarios=None):
        # Get test case result from cache if all test case results were already
        # retrieved for given Subject.
        cache_key = (subject.type, subject.identifier, scenarios)
        if testcase and cache_key in self.cache:
            for result in self.cache[cache_key]:
                if result['testcase']['name'] == testcase:
                    return [result]
            return []

        params = {
            '_distinct_on': 'scenario,system_architecture,system_variant'
        }
        if self.since:
            params.update({'since': self.since})
        if testcase:
            params.update({'testcases': testcase})
        if scenarios:
            params.update({'scenario': ','.join(scenarios)})

        results = []
        for query in subject.result_queries():
            query.update(params)
            results.extend(self._retrieve_data(query))

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
            json={'filters': params},
            **request_args)


class NoSourceException(RuntimeError):
    pass


@cached
def retrieve_scm_from_koji(nvr):
    """ Retrieve cached rev and namespace from koji using the nvr """
    koji_url = current_app.config['KOJI_BASE_URL']
    try:
        proxy = xmlrpc.client.ServerProxy(koji_url)
        build = proxy.getBuild(nvr)
    except (xmlrpc.client.ProtocolError, socket.error) as err:
        raise ConnectionError('Could not reach Koji: {}'.format(err))
    return retrieve_scm_from_koji_build(nvr, build, koji_url)


def retrieve_scm_from_koji_build(nvr, build, koji_url):
    if not build:
        raise NotFound('Failed to find Koji build for "{}" at "{}"'.format(nvr, koji_url))

    source = None
    try:
        source = build['extra']['source']['original_url']
    except (TypeError, KeyError, AttributeError):
        pass
    finally:
        if not source:
            source = build.get('source')

    if not source:
        raise NoSourceException(
            'Failed to retrieve SCM URL from Koji build "{}" at "{}" '
            '(expected SCM URL in "source" attribute)'.format(nvr, koji_url)
        )

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
            '(missing URL fragment with SCM revision information)'.format(source, nvr, koji_url)
        )

    pkg_name = url.path.split('/')[-1]
    pkg_name = re.sub(r'\.git$', '', pkg_name)
    return namespace, pkg_name, rev


@cached
def retrieve_yaml_remote_rule(rev, pkg_name, pkg_namespace, url_template):
    """ Retrieve a remote rule file content from the git web UI. """
    data = {
        "pkg_namespace": pkg_namespace + ('/' if pkg_namespace else ''),
        "pkg_name": pkg_name,
        "rev": rev
    }
    url = url_template.format(**data)
    response = requests_session.request('HEAD', url)
    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise BadGateway('Error occurred while retrieving a remote rule file from the repo.')

    # remote rule file found...
    response = requests_session.request('GET', url)
    response.raise_for_status()
    return response.content


# NOTE - not cached.
def retrieve_decision(greenwave_url, data):
    response = requests_session.post(greenwave_url, json=data)
    response.raise_for_status()
    return response.json()
