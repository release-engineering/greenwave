# SPDX-License-Identifier: GPL-2.0+

import pytest
from defusedxml.xmlrpc import xmlrpc_client
from werkzeug.exceptions import BadGateway, BadRequest

from greenwave.resources import retrieve_koji_build_task_id


@pytest.mark.parametrize(
    "subject",
    (
        None,
        123,
        "null",
        "bad_subject",
        # A bare package name is not a valid NVR: name, version and release
        # must be separated by dashes.
        "pki-core",
        "nethack-1.2.3",
        # Empty release.
        "nethack-1.2.3-",
        # Empty version.
        "nethack--1",
    ),
)
def test_koji_bad_nvr(app, koji_proxy, subject):
    expected = "Invalid NVR format: "
    with pytest.raises(BadRequest, match=expected):
        retrieve_koji_build_task_id(subject, "https://localhost:5006/kojihub")


@pytest.mark.parametrize(
    "nvr",
    (
        "nethack-1.2.3-1.rawhide",
        # Package name may contain dashes.
        "pki-core-10.5.1-1.el8",
        # Draft build.
        "freerdp-2.1.1-5.el7_9.14,draft_4144991",
        # Epoch is a part of the name for koji.parse_NVR().
        "1:foo-1.0-1",
        # Name may be empty for koji.parse_NVR().
        "-1.0-1",
    ),
)
def test_koji_good_nvr(app, koji_proxy, nvr):
    """NVRs accepted by koji.parse_NVR() are passed to the Koji API."""
    retrieve_koji_build_task_id(nvr, "https://localhost:5006/kojihub")
    koji_proxy.getBuild.assert_called_once_with(nvr)


def test_koji_fault(app, koji_proxy):
    expected = "Failed to get Koji build"
    koji_proxy.getBuild.side_effect = xmlrpc_client.Fault(1000, "invalid format")
    with pytest.raises(BadGateway, match=expected):
        retrieve_koji_build_task_id(
            "nethack-1.2.3-1.rawhide", "https://localhost:5006/kojihub"
        )
