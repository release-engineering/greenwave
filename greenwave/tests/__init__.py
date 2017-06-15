# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Greenwave uses the Python `unittest`_ framework for unit tests.

Patches should be accompanied by one or more tests to demonstrate the feature
or bugfix works. This makes the review process much easier since it allows the
reviewer to run your code with very little effort, and it lets developers know
when they break your code.


Running Tests
=============

Tests are run with `py.test`_ via `tox`_. You can run individual environments by
using the ``-e`` flag. For example, ``tox -e lint`` runs the linter.


Test Organization
=================

The test organization is as follows:

1. Each module in the application has a corresponding test module. These
   modules is organized in the test package to mirror the package they test.
   That is, ``greenwave/app.py`` has a test module in located at
   ``greenwave/tests/test_app.py``

2. Within each test module, follow the unittest code organization guidelines.

3. Include documentation blocks for each test case that explain the goal of the
   test.


.. _unittest: https://docs.python.org/3/library/unittest.html
.. _py.test: https://docs.pytest.org/en/latest/
.. _tox: https://tox.readthedocs.io/en/latest/
"""
