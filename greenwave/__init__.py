# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Greenwave is a web application built using `Flask`_ and `SQLAlchemy`_.

It provides a :ref:`http-api` for applications to use.

.. _Flask: http://flask.pocoo.org/
.. _SQLAlchemy: http://sqlalchemy.org/
"""
import importlib.metadata as importlib_metadata

try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:
    # If the app is not installed but run from git repository clone, get the
    # version from pyproject.toml.
    try:
        import tomllib
    except ImportError:
        import toml as tomllib  # type: ignore

    with open("pyproject.toml", "r") as f:
        pyproject = tomllib.load(f)  # type: ignore

    __version__ = pyproject["tool"]["poetry"]["version"]
