=================
Development Guide
=================

If you would like to write a patch for Greenwave, this document will help you
get started.


Quick development setup
=======================

As an alternative to using virtualenv, described below, you can install system
packages listed in Dockerfile.

Set up Python 3 vitualenv:

.. code-block:: console

   $ python3 -m venv --system-site-packages .venv
   $ source .venv/bin/activate

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

You can run the unit tests, which live in the ``greenwave.tests`` package, with
the following command:

.. code-block:: console

   $ poetry run pytest greenwave

There are also functional tests in the :file:`functional-tests` directory. The
functional tests will start their own copy of the `ResultsDB`_, `WaiverDB`_,
and Greenwave servers and then send HTTP requests to them.

You can run the functional tests like this:

.. code-block:: console

   $ poetry run pytest functional-tests

The functional tests assume you have ResultsDB and WaiverDB git checkouts in
:file:`../resultsdb` and :file:`../waiverdb` respectively. You can tell it to
find them in a different location by passing ``RESULTSDB`` or ``WAIVERDB``
environment variables.

You can quickly clone the repositories (to parent directory) and update
development virtualenv with:

.. code-block:: console

   $ git clone https://github.com/release-engineering/waiverdb.git ../waiverdb/
   $ git clone https://github.com/release-engineering/resultsdb.git ../resultsdb/
   $ poetry run pip install -r ../waiverdb/requirements.txt
   $ poetry run pip install -r ../resultsdb/requirements.txt

If you'd rather not install all the dependencies necessary to run the functional
tests, you may use Vagrant to provision a throw-away virtual machine to run
the tests:

.. toctree::
   :maxdepth: 2

   vagrant

You should run smoke test after deploying on stage:

.. code-block:: console

    $ export GREENWAVE_TEST_URL=https://greenwave.stg.fedoraproject.org/
    $ export WAIVERDB_TEST_URL=https://waiverdb.stg.fedoraproject.org/
    $ py.test-3 functional-tests -m smoke

Docker Compose
==============

For local development, you may want to easily bring up containers of
WaiverDB, ResultsDB, and/or Greenwave. For more information on that, see:

.. toctree::
   :maxdepth: 2

   docker-compose

Building the documentation
==========================

The documentation is built using `Sphinx`_. If you've made changes to the
documentation, you can build it locally and view it in your browser:

.. code-block:: console

   $ cd docs
   $ make html
   $ firefox _build/html/index.html


Code style
==========

We follow the `PEP 8`_ style guide for Python. You can check your code's style
using flake8:

.. code-block:: console

   $ poetry run flake8

Additionally, we follow the `"Google style" for docstrings
<http://www.sphinx-doc.org/en/latest/ext/example_google.html>`_.


.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _ResultsDB: https://github.com/release-engineering/resultsdb
.. _WaiverDB: https://github.com/release-engineering/waiverdb
.. _Sphinx: http://www.sphinx-doc.org/
