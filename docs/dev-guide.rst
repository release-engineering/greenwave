=================
Development Guide
=================

If you would like to write a patch for Greenwave, this document will help you
get started.

Development setup
=================

Install development dependencies:

.. code-block:: console

   $ poetry install --no-root

Create a local configuration file:

.. code-block:: console

   $ cp conf/settings.py.example conf/settings.py

Run the server:

.. code-block:: console

   $ DEV=true poetry run python3 run-dev-server.py

The server is now running at <http://localhost:5005> and API calls can be sent to
<http://localhost:5005/api/v1.0>.

Running the tests
=================

Run tests using ``tox`` command.

To run only specific tests:

.. code-block:: console

   $ tox -e py39 -- --no-cov -k test_waive_scenario

Functional Tests
================

Functional tests extend the basic unit test suite and additionally verify
proper communication with `WaiverDB`_, `ResultsDB`_ and message bus.

For local development, you may want to easily bring up containers of
`WaiverDB`_, `ResultsDB`_, and/or Greenwave. For more information on that, see:

.. toctree::
   :maxdepth: 2

   docker-compose

Building the documentation
==========================

The documentation is built using `Sphinx`_. If you've made changes to the
documentation, you can build it locally and view it in your browser:

.. code-block:: console

   $ tox -e docs
   $ open docs/_build/html/index.html

Code style
==========

We follow the `PEP 8`_ style guide for Python. You can check your code's style
using flake8:

.. code-block:: console

   $ tox -e flake8

Additionally, we follow the `"Google style" for docstrings
<http://www.sphinx-doc.org/en/latest/ext/example_google.html>`_.


.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _ResultsDB: https://github.com/release-engineering/resultsdb
.. _WaiverDB: https://github.com/release-engineering/waiverdb
.. _Sphinx: http://www.sphinx-doc.org/
