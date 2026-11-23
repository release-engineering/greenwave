# SPDX-License-Identifier: GPL-2.0+


import pytest

from greenwave import product_versions
from greenwave.app_factory import create_app
from greenwave.product_versions import subject_product_versions
from greenwave.subjects.factory import create_subject


def mock_subject():
    return create_subject("koji_build", "nethack-1.2.3-1.rawhide")


@pytest.mark.parametrize(
    "brew_pv, expected_pvs",
    (
        ("rawhide", ["fedora-rawhide"]),
        ("f35-candidate", ["fedora-35"]),
        ("epel7-candidate", ["epel-7"]),
        ("rhel-8.5.0-candidate", ["rhel-8", "rhel-8.5"]),
        ("rhel-9.2.0-beta-candidate", ["rhel-9", "rhel-9.2"]),
    ),
)
def test_guess_koji_build_product_version(brew_pv, expected_pvs, koji_proxy, app):
    koji_proxy.getTaskRequest.return_value = [
        "git://pkgs.devel.example.com/rpms/nethack#12345abcde",
        brew_pv,
        {"scratch": False},
    ]
    pvs = product_versions._guess_koji_build_product_versions(
        mock_subject(), "https://localhost:5006/kojihub", koji_task_id=1
    )
    assert pvs == expected_pvs


@pytest.mark.parametrize("task_id", (None, 3))
def test_guess_koji_build_product_version_socket_error(task_id, koji_proxy, app):
    koji_proxy.getBuild.side_effect = koji_proxy.getTaskRequest.side_effect = (
        TimeoutError("timed out")
    )
    expected = "Could not reach Koji: timed out"
    with pytest.raises(ConnectionError, match=expected):
        # pylint: disable=protected-access
        product_versions._guess_koji_build_product_versions(
            mock_subject(), "https://localhost:5006/kojihub", task_id
        )


def test_guess_product_version_with_koji(koji_proxy, app):
    koji_proxy.getBuild.return_value = {"task_id": 666}
    koji_proxy.getTaskRequest.return_value = [
        "git://example.com/project",
        "rawhide",
        {},
    ]

    subject = mock_subject()
    product_versions = subject_product_versions(
        subject, "https://localhost:5006/kojihub"
    )

    koji_proxy.getBuild.assert_called_once_with(subject.item)
    koji_proxy.getTaskRequest.assert_called_once_with(666)
    assert product_versions == ["fedora-rawhide"]


def test_guess_product_version_with_koji_without_task_id(koji_proxy, app):
    koji_proxy.getBuild.return_value = {"task_id": None}

    subject = create_subject("koji_build", "nethack-1.2.3-1.test")
    product_versions = subject_product_versions(
        subject, "https://localhost:5006/kojihub"
    )

    koji_proxy.getBuild.assert_called_once_with(subject.item)
    koji_proxy.getTaskRequest.assert_not_called()
    assert product_versions == []


@pytest.mark.parametrize(
    "task_request",
    (
        ["git://example.com/project", 7777, {}],
        [],
        None,
    ),
)
def test_guess_product_version_with_koji_and_unexpected_task_type(
    task_request, koji_proxy, app
):
    koji_proxy.getBuild.return_value = {"task_id": 666}
    koji_proxy.getTaskRequest.return_value = task_request

    subject = create_subject("koji_build", "nethack-1.2.3-1.test")
    product_versions = subject_product_versions(
        subject, "https://localhost:5006/kojihub"
    )

    koji_proxy.getBuild.assert_called_once_with(subject.item)
    koji_proxy.getTaskRequest.assert_called_once_with(666)
    assert product_versions == []


@pytest.mark.parametrize(
    "nvr, expected_product_versions",
    (
        ("nethack-1.2.3-1.el10", ["rhel-10"]),
        ("nethack-1.2.3-1.el10,draft_123", ["rhel-10"]),
        ("anaconda-34.25.7.20-1.el9,draft_4134868", ["rhel-9"]),
        ("kernel-6.12.0-211.71.1.el10_2,draft_4146901", ["rhel-10"]),
        ("cloud-init-24.4-6.el10_1.2,draft_3983663", ["rhel-10"]),
        ("cloud-init-24.4-6.el10_1.2", ["rhel-10"]),
        ("freerdp-2.1.1-5.el7_9.14,draft_4144991", ["rhel-7"]),
        # Release can contain extra dot-separated components before the
        # product version.
        ("nmstate-2.2.64-0.20261123.2888git847992c2.el10", ["rhel-10"]),
    ),
)
def test_guess_product_version_from_nvr(nvr, expected_product_versions, app):
    subject = create_subject("koji_build", nvr)
    product_versions = subject_product_versions(subject)
    assert product_versions == expected_product_versions


@pytest.mark.parametrize(
    "nvr",
    (
        "badnvr.elastic-1-228",
        "badnvr-1.2-1.elastic8",
        "el99",
        "badnvr-1.2.f30",
    ),
)
def test_guess_product_version_failure(nvr):
    app = create_app()
    with app.app_context():
        subject = create_subject("koji_build", nvr)
    product_versions = subject_product_versions(subject)
    assert product_versions == []
