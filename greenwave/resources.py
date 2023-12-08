# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import datetime
import logging
import re
import socket
import threading
from typing import List, Optional

from dateutil import tz
from dateutil.parser import parse
from defusedxml.xmlrpc import xmlrpc_client
from urllib.parse import urlparse
from flask import current_app
from opentelemetry import trace
from werkzeug.exceptions import BadGateway, NotFound

from greenwave.cache import cached
from greenwave.request_session import get_requests_session
from greenwave.xmlrpc_server_proxy import get_server_proxy

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

requests_session = threading.local().requests_session = get_requests_session()


def _koji(uri: str):
    """
    Returns per-thread cached XMLRPC server proxy object for Koji.
    """
    data = threading.local()
    try:
        return data.koji_server_proxy_cache
    except AttributeError:
        proxy = get_server_proxy(uri, _requests_timeout())
        data.koji_server_proxy_cache = proxy
        return proxy


def _requests_timeout():
    timeout = current_app.config['REQUESTS_TIMEOUT']
    if isinstance(timeout, tuple):
        return timeout[1]
    return timeout


def _raise_for_status(response):
    if response.ok:
        return

    msg = (
        f"Got unexpected status code {response.status_code} for"
        f" {response.url}: {response.text}"
    )
    log.error(msg)
    raise BadGateway(msg)


class BaseRetriever:
    ignore_ids: List[int]
    url: str
    since: Optional[str]

    def __init__(self, ignore_ids: List[int], when: str, url: str):
        self.ignore_ids = ignore_ids
        self.url = url

        if when:
            self.since = '1900-01-01T00:00:00.000000,{}'.format(when)
        else:
            self.since = None

    @tracer.start_as_current_span("retrieve")
    def retrieve(self, *args, **kwargs):
        items = self._retrieve_all(*args, **kwargs)
        return [item for item in items if item['id'] not in self.ignore_ids]

    def _retrieve_data(self, params):
        response = self._make_request(params)
        _raise_for_status(response)
        return response.json()['data']


class ResultsRetriever(BaseRetriever):
    """
    Retrieves results from cache or ResultsDB.
    """

    def __init__(self, **args):
        super().__init__(**args)
        self._distinct_on = ','.join(
            current_app.config['DISTINCT_LATEST_RESULTS_ON'])
        self.cache = {}

    def _retrieve_all(self, subject, testcase=None):
        # Get test case result from cache if all test case results were already
        # retrieved for given Subject.
        cache_key = (subject.type, subject.identifier)
        if testcase and cache_key in self.cache:
            return [res for res in self.cache[cache_key] if res['testcase']['name'] == testcase]

        # Try to get passing test case result from external cache.
        external_cache_key = None
        if testcase:
            external_cache_key = (
                "greenwave.resources:ResultsRetriever|"
                f"{subject.type} {subject.identifier} {testcase}")
            results = self.get_external_cache(external_cache_key)
            if results and self._results_match_time(results):
                return results

        params = {
            '_distinct_on': self._distinct_on
        }
        if self.since:
            params.update({'since': self.since})
        if testcase:
            params.update({'testcases': testcase})

        results = []
        for query in subject.result_queries():
            query.update(params)
            results.extend(self._retrieve_data(query))

        if not testcase:
            self.cache[cache_key] = results

        # Store test case results in external cache if all are passing,
        # otherwise retrieve from ResultsDB again later.
        if external_cache_key and all(
                result.get('outcome') in current_app.config['OUTCOMES_PASSED']
                for result in results):
            self.set_external_cache(external_cache_key, results)

        return results

    def _make_request(self, params, **request_args):
        return requests_session.get(
            self.url + '/results/latest',
            params=params,
            **request_args)

    def _results_match_time(self, results):
        if not self.since:
            return True

        until = self.since.split(',')[1]
        return all(result['submit_time'] < until for result in results)

    def get_external_cache(self, key):
        return current_app.cache.get(key)

    def set_external_cache(self, key, value):
        current_app.cache.set(key, value)


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


class KojiScmUrlParseError(BadGateway):
    """
    Exception raised when parsing SCM revision from Koji build fails.
    """
    pass


@cached
def retrieve_koji_build_target(task_id, koji_url: str):
    log.debug('Getting Koji task request ID %r', task_id)
    proxy = _koji(koji_url)
    task_request = proxy.getTaskRequest(task_id)
    if isinstance(task_request, list) and len(task_request) > 1:
        target = task_request[1]
        if isinstance(target, str):
            return target
    return None


@cached
def _retrieve_koji_build_attributes(nvr: str, koji_url: str):
    log.debug('Getting Koji build %r', nvr)
    proxy = _koji(koji_url)
    build = proxy.getBuild(nvr)
    if not build:
        raise NotFound(
            'Failed to find Koji build for "{}" at "{}"'.format(nvr, koji_url)
        )

    task_id = build.get("task_id")

    source = build.get("source")
    if not source:
        try:
            source = build["extra"]["source"]["original_url"]
        except (TypeError, KeyError, AttributeError):
            source = None

    creation_time = build.get('creation_time')

    return (task_id, source, creation_time)


def retrieve_koji_build_task_id(nvr: str, koji_url: str):
    return _retrieve_koji_build_attributes(nvr, koji_url)[0]


def retrieve_koji_build_source(nvr: str, koji_url: str):
    return _retrieve_koji_build_attributes(nvr, koji_url)[1]


def retrieve_koji_build_creation_time(nvr: str, koji_url: str):
    creation_time = _retrieve_koji_build_attributes(nvr, koji_url)[2]
    try:
        time = parse(str(creation_time))
        if time.tzinfo is None:
            time = time.replace(tzinfo=tz.tzutc())
        return time
    except ValueError:
        log.warning(
            'Could not parse Koji build creation_time %r for nvr %r',
            creation_time, nvr
        )

    return datetime.datetime.now(tz.tzutc())


def retrieve_scm_from_koji(nvr: str):
    """Retrieve cached rev and namespace from koji using the nvr"""
    koji_url = current_app.config["KOJI_BASE_URL"]
    try:
        source = retrieve_koji_build_source(nvr, koji_url)
    except (xmlrpc_client.ProtocolError, socket.error) as err:
        raise ConnectionError("Could not reach Koji: {}".format(err))
    return retrieve_scm_from_koji_build(nvr, source, koji_url)


def retrieve_scm_from_koji_build(nvr: str, source: str, koji_url: str):
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
        raise KojiScmUrlParseError(
            'Failed to parse SCM URL "{}" from Koji build "{}" at "{}" '
            '(missing URL fragment with SCM revision information)'.format(source, nvr, koji_url)
        )

    pkg_name = url.path.split('/')[-1]
    pkg_name = re.sub(r'\.git$', '', pkg_name)
    return namespace, pkg_name, rev


@cached
def retrieve_yaml_remote_rule(url: str):
    """ Retrieve a remote rule file content from the git web UI. """
    response = requests_session.request('HEAD', url)
    if response.status_code == 404:
        log.debug('Remote rule not found: %s', url)
        return None

    if response.status_code != 200:
        raise BadGateway('Error occurred while retrieving a remote rule file from the repo.')

    # remote rule file found...
    response = requests_session.request('GET', url)
    _raise_for_status(response)
    return response.content
