# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-2.0+
"""
Greenwave is a web application built using `Flask`_ and `SQLAlchemy`_.

It provides a :ref:`http-api` for applications to use.

.. _Flask: http://flask.pocoo.org/
.. _SQLAlchemy: http://sqlalchemy.org/
"""
import importlib.metadata as importlib_metadata

__version__ = importlib_metadata.version(__name__)
