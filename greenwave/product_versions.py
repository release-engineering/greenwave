# SPDX-License-Identifier: GPL-2.0+
"""
Product version guessing for subject identifiers
"""

import logging
import re
import socket
import xmlrpc.client

from werkzeug.exceptions import NotFound

from greenwave.resources import (
    retrieve_koji_build_target,
    retrieve_koji_build_task_id,
)

log = logging.getLogger(__name__)


def _guess_product_version(toparse, koji_build=False):
    if toparse == 'rawhide' or toparse.startswith('Fedora-Rawhide'):
        return 'fedora-rawhide'

    product_version = None
    if toparse.startswith('f') and koji_build:
        product_version = 'fedora-'
    elif toparse.startswith('epel'):
        product_version = 'epel-'
    elif toparse.startswith('el') and len(toparse) > 2 and toparse[2].isdigit():
        product_version = 'rhel-'
    elif toparse.startswith('rhel-') and len(toparse) > 5 and toparse[5].isdigit():
        product_version = 'rhel-'
    elif toparse.startswith('fc') or toparse.startswith('Fedora'):
        product_version = 'fedora-'

    if product_version:
        # seperate the prefix from the number
        result = list(filter(None, '-'.join(re.split(r'(\d+)', toparse)).split('-')))
        if len(result) >= 2:
            try:
                int(result[1])
                product_version += result[1]
                return product_version
            except ValueError:
                pass

    log.error("It wasn't possible to guess the product version")
    return None


def _guess_koji_build_product_version(
        subject_identifier, koji_base_url, koji_task_id=None):
    try:
        if not koji_task_id:
            log.debug('Getting Koji task ID for build %r', subject_identifier)
            try:
                koji_task_id = retrieve_koji_build_task_id(
                    subject_identifier, koji_base_url
                )
            except NotFound:
                koji_task_id = None

            if not koji_task_id:
                return None

        target = retrieve_koji_build_target(koji_task_id, koji_base_url)
        if target:
            return _guess_product_version(target, koji_build=True)

        return None
    except (xmlrpc.client.ProtocolError, socket.error) as err:
        raise ConnectionError('Could not reach Koji: {}'.format(err))
    except xmlrpc.client.Fault:
        log.exception('Unexpected Koji XML RPC fault')


def subject_product_version(
        subject,
        koji_base_url=None,
        koji_task_id=None):
    if subject.product_version:
        return subject.product_version

    if subject.short_product_version:
        product_version = _guess_product_version(
            subject.short_product_version, koji_build=subject.is_koji_build)
        if product_version:
            return product_version

    if koji_base_url and subject.is_koji_build:
        return _guess_koji_build_product_version(
            subject.identifier, koji_base_url, koji_task_id)
