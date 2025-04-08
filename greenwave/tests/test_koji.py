# SPDX-License-Identifier: GPL-2.0+

import pytest
from werkzeug.exceptions import BadRequest

from greenwave.resources import retrieve_koji_build_task_id


@pytest.mark.parametrize(
    "subject",
    (
        None,
        123,
        "null",
        "bad_subject",
    ),
)
def test_koji_bad_nvr(app, subject):
    expected = "Invalid NVR format: "
    with pytest.raises(BadRequest, match=expected):
        retrieve_koji_build_task_id(subject, "https://localhost:5006/kojihub")
