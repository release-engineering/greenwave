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
        subject_identifier,
        subject_type,
        koji_proxy=None,
        koji_task_id=None):
    if subject_type == 'koji_build':
        try:
            _, _, release = subject_identifier.rsplit('-', 2)
            _, short_prod_version = release.rsplit('.', 1)
            return _guess_product_version(short_prod_version, koji_build=True)
        except (KeyError, ValueError):
            pass

    if subject_type == "compose":
        return _guess_product_version(subject_identifier)

    if subject_type in ("redhat-module", "redhat-container-image"):
        return "rhel-8"

    if koji_proxy:
        return _guess_koji_build_product_version(
            subject_identifier, koji_proxy, koji_task_id)
