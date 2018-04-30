
# SPDX-License-Identifier: GPL-2.0+

import pytest

from greenwave.utils import retry


def test_retry_passthrough():
    """ Ensure that retry doesn't gobble exceptions. """
    expected = "This is the exception."

    @retry(timeout=0.1, interval=0.1, wait_on=Exception)
    def f():
        raise Exception(expected)

    with pytest.raises(Exception) as actual:
        f()

    assert expected in str(actual)


def test_retry_count():
    """ Ensure that retry doesn't gobble exceptions. """
    expected = "This is the exception."

    calls = []

    @retry(timeout=0.3, interval=0.1, wait_on=Exception)
    def f():
        calls.append(1)
        raise Exception(expected)

    with pytest.raises(Exception):
        f()

    assert sum(calls) == 3
