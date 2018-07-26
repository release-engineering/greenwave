# SPDX-License-Identifier: GPL-2.0+
""" Greenwave resources.

This module contains routines for interacting with other services (resultsdb,
waiverdb, etc..).

"""

import logging
import json
import requests
import urllib3.exceptions

from urllib.parse import urlparse, urljoin
import xmlrpc.client
from flask import current_app
from werkzeug.exceptions import BadGateway

from greenwave.cache import cached
import greenwave.utils

log = logging.getLogger(__name__)

requests_session = requests.Session()


@cached
@greenwave.utils.retry(wait_on=urllib3.exceptions.NewConnectionError)
def retrieve_scm_from_koji(nvr):
    """ Retrieve cached rev and namespace from koji using the nvr """
    proxy = xmlrpc.client.ServerProxy(current_app.config['KOJI_BASE_URL'])
    build = proxy.getBuild(nvr)

    if not build:
        raise BadGateway("Found %s when looking for %s at %s" % (
            build, nvr, current_app.config['KOJI_BASE_URL']))

    try:
        url = urlparse(build['source'])

        if not url.scheme.startswith('git'):
            raise BadGateway('Unable to extract scm from koji.  '
                             '%s doesn\'t begin with git://' % url)

        rev = url.fragment
        namespace = url.path.split('/')[-2]
        return namespace, rev
    except Exception:
        error = 'Error occurred looking for the "rev" in koji.'
        log.exception(error)
        raise BadGateway(error)


@cached
def retrieve_yaml_remote_rule(rev, pkg_name, pkg_namespace):
    """ Retrieve cached gating.yaml content for a given rev. """
    data = {
        "DIST_GIT_BASE_URL": current_app.config['DIST_GIT_BASE_URL'].rstrip('/') + '/',
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


def retrieve_builds_in_update(update_id):
    """
    Queries Bodhi to find the list of builds in the given update.
    Returns a list of build NVRs.
    """
    if not current_app.config['BODHI_URL']:
        log.warning('Making a decision about Bodhi update %s '
                    'but Bodhi integration is disabled! '
                    'Assuming no builds in update',
                    update_id)
        return []
    update_info_url = urljoin(current_app.config['BODHI_URL'],
                              '/updates/{}'.format(update_id))
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    response = requests_session.get(update_info_url,
                                    headers={'Accept': 'application/json'},
                                    timeout=timeout, verify=verify)

    # Ignore failures to retrieve Bodhi update.
    if not response.ok:
        log.warning(
            'Making a decision about Bodhi update %s failed: %r',
            update_id, response)
        return []

    return [build['nvr'] for build in response.json()['update']['builds']]


def retrieve_update_for_build(nvr):
    """
    Queries Bodhi to find the update which the given build is in (if any).
    Returns a Bodhi updateid, or None if the build is not in any update.
    """
    updates_list_url = urljoin(current_app.config['BODHI_URL'], '/updates/')
    params = {'builds': nvr}
    timeout = current_app.config['REQUESTS_TIMEOUT']
    verify = current_app.config['REQUESTS_VERIFY']
    response = requests_session.get(updates_list_url,
                                    params=params,
                                    headers={'Accept': 'application/json'},
                                    timeout=timeout, verify=verify)
    response.raise_for_status()
    matching_updates = response.json()['updates']
    if matching_updates:
        return matching_updates[0]['updateid']
    return None


def retrieve_item_results(item):
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


@cached
def retrieve_results(subject_type, subject_identifier):
    """
    Returns all results from ResultsDB which might be relevant for the given
    decision subject, accounting for all the different possible ways in which
    test results can be reported.
    """
    # Note that the reverse of this logic also lives in the
    # announcement_subjects() method of the Resultsdb consumer (it has to map
    # from a newly received result back to the possible subjects it is for).
    results = []
    if subject_type == 'bodhi_update':
        results.extend(retrieve_item_results(
            {'type': 'bodhi_update', 'item': subject_identifier}))
    elif subject_type == 'koji_build':
        results.extend(retrieve_item_results({'type': 'koji_build', 'item': subject_identifier}))
        results.extend(retrieve_item_results({'type': 'brew-build', 'item': subject_identifier}))
        results.extend(retrieve_item_results({'original_spec_nvr': subject_identifier}))
    elif subject_type == 'compose':
        results.extend(retrieve_item_results({'productmd.compose.id': subject_identifier}))
        results.extend(retrieve_item_results({'type': 'compose', 'item': subject_identifier}))
    else:
        raise RuntimeError('Unhandled subject type %r' % subject_type)
    return results


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
