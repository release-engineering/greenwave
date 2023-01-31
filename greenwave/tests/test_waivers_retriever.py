# SPDX-License-Identifier: GPL-2.0+

import mock
from typing import Any, Dict

from greenwave.resources import WaiversRetriever

_DUMMY_RETRIEVER_ARGUMENTS: Dict[str, Any] = dict(
    ignore_ids=[],
    when=None,
    url=None,
)

_DUMMY_FILTERS = ['dummy_filter']


def test_waivers_retriever_retrieves_not_ignored_ids():
    # pylint: disable=protected-access
    retriever = WaiversRetriever(**_DUMMY_RETRIEVER_ARGUMENTS)
    retriever.ignore_ids = [100]
    waiver = dict(
        id=99,
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        product_version='rawhide',
        testcase='test1',
        waived=True,
    )
    retriever._retrieve_data = mock.MagicMock(return_value=[waiver])
    waivers = retriever.retrieve(_DUMMY_FILTERS)
    assert [waiver] == waivers


def test_waivers_retriever_ignores_ids():
    # pylint: disable=protected-access
    retriever = WaiversRetriever(**_DUMMY_RETRIEVER_ARGUMENTS)
    retriever.ignore_ids = [99]
    waiver = dict(
        id=99,
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        product_version='rawhide',
        testcase='test1',
        waived=True,
    )
    retriever._retrieve_data = mock.MagicMock(return_value=[waiver])
    waivers = retriever.retrieve(_DUMMY_FILTERS)
    assert [] == waivers


def test_waivers_retriever_ignores_no_waived():
    # pylint: disable=protected-access
    retriever = WaiversRetriever(**_DUMMY_RETRIEVER_ARGUMENTS)
    waiver = dict(
        id=99,
        subject_type='koji_build',
        subject_identifier='nethack-1.2.3-1.rawhide',
        product_version='rawhide',
        testcase='test1',
        waived=False,
    )
    retriever._retrieve_data = mock.MagicMock(return_value=[waiver])
    waivers = retriever.retrieve(_DUMMY_FILTERS)
    assert [] == waivers
