# SPDX-License-Identifier: GPL-2.0+
"""
Product version guessing for subject identifiers
"""

import logging
import re

import xmlrpc.client

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
        subject_identifier, koji_proxy, koji_task_id=None):
    try:
        if not koji_task_id:
            build = koji_proxy.getBuild(subject_identifier) or {}
            koji_task_id = build.get('task_id')
            if not koji_task_id:
                return None

        target = koji_proxy.getTaskRequest(koji_task_id)[1]
        return _guess_product_version(target, koji_build=True)
    except xmlrpc.client.Fault:
        pass


def subject_product_version(
        subject,
        koji_proxy=None,
        koji_task_id=None):
    if subject.product_version:
        return subject.product_version

    if subject.short_product_version:
        product_version = _guess_product_version(
            subject.short_product_version, koji_build=subject.is_koji_build)
        if product_version:
            return product_version

    if koji_proxy and subject.is_koji_build:
        return _guess_koji_build_product_version(
            subject.identifier, koji_proxy, koji_task_id)
