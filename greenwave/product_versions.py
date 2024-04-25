# SPDX-License-Identifier: GPL-2.0+
"""
Product version guessing for subject identifiers
"""

import logging
import re

from defusedxml.xmlrpc import xmlrpc_client
from werkzeug.exceptions import BadGateway, NotFound

from greenwave.resources import (
    retrieve_koji_build_target,
    retrieve_koji_build_task_id,
)

log = logging.getLogger(__name__)


def _guess_product_versions(toparse, koji_build=False) -> list[str]:
    if toparse == "rawhide" or toparse.startswith("Fedora-Rawhide"):
        return ["fedora-rawhide"]

    product_version = None
    if toparse.startswith("f") and koji_build:
        product_version = "fedora-"
    elif toparse.startswith("epel"):
        product_version = "epel-"
    elif toparse.startswith("el") and len(toparse) > 2 and toparse[2].isdigit():
        product_version = "rhel-"
    elif toparse.startswith("rhel-") and len(toparse) > 5 and toparse[5].isdigit():
        product_version = "rhel-"
    elif toparse.startswith("fc") or toparse.startswith("Fedora"):
        product_version = "fedora-"

    if product_version:
        # seperate the prefix from the number
        result = list(filter(None, "-".join(re.split(r"(\d+)", toparse)).split("-")))
        if len(result) >= 2:
            try:
                int(result[1])
                product_version += result[1]
                return [product_version]
            except ValueError:
                pass

    log.warning("Failed to guess the product version for %s", toparse)
    return []


def _guess_koji_build_product_versions(
    subject, koji_base_url, koji_task_id=None
) -> list[str]:
    try:
        if not koji_task_id:
            try:
                koji_task_id = retrieve_koji_build_task_id(
                    subject.identifier, koji_base_url
                )
            except NotFound:
                koji_task_id = None

            if not koji_task_id:
                return []

        target = retrieve_koji_build_target(koji_task_id, koji_base_url)
        if target:
            pvs = subject.product_versions_from_koji_build_target(target)
            if pvs:
                return pvs
            return _guess_product_versions(target, koji_build=True)

        return []
    except (xmlrpc_client.ProtocolError, OSError) as err:
        raise ConnectionError(f"Could not reach Koji: {err}")
    except BadGateway:
        log.warning("Failed to get product version from Koji")
        return []


def subject_product_versions(
    subject, koji_base_url=None, koji_task_id=None
) -> list[str]:
    if subject.product_versions:
        return subject.product_versions

    if koji_base_url and subject.is_koji_build:
        pvs = _guess_koji_build_product_versions(subject, koji_base_url, koji_task_id)
        if pvs:
            return pvs

    if subject.short_product_version:
        return _guess_product_versions(
            subject.short_product_version, koji_build=subject.is_koji_build
        )

    return []
