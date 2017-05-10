=======================
Contribution Guidelines
=======================

Please follow the following contribution guidelines when contributing a pull
request.


Code style
==========

We follow the `PEP 8`_ style guide for Python. The test suite includes a test
that enforces the required style, so all you need to do is run the tests to
ensure your code follows the style. If the unit test passes, you are good to go!


Unit tests
==========

.. automodule:: greenwave.tests


Documentation
=============
Greenwave uses `sphinx <http://www.sphinx-doc.org/>`_ to create its documentation.
New packages, modules, classes, methods, functions, and attributes all should be
documented using `"Google style" <http://www.sphinx-doc.org/en/latest/ext/example_google.html>`_
docstrings.

Python API documentation is automatically generated from the code using Sphinx's
`autodoc <http://www.sphinx-doc.org/en/stable/tutorial.html#autodoc>`_ extension.
HTTP REST API documentation is automatically generated from the code using the
`httpdomain <http://pythonhosted.org/sphinxcontrib-httpdomain/>`_ extension.


Development Environment
=======================

Set up a Python virtual environment and then install Greenwave::

  $ pip install -r dev-requirements.txt
  $ pip install -e .


.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
