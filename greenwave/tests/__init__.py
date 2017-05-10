# -*- coding: utf-8 -*-
#
# This file is part of the Greenwave project.
# Copyright (C) 2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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
