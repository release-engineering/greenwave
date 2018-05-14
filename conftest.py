# SPDX-License-Identifier: GPL-2.0+

import pytest


@pytest.fixture(autouse=True)
def set_environment_variable(monkeypatch):
    monkeypatch.setenv('TEST', 'true')
